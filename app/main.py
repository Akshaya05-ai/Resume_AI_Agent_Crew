import os
from dotenv import load_dotenv
load_dotenv()
import traceback
import threading
import time
import logging
from typing import List, Optional
from fastapi import FastAPI, Depends, File, UploadFile, Form, Header, HTTPException, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import init_db, get_db, User, Resume, Report, CareerActivity
from app.auth import router as auth_router, get_current_user
from app.parser import parse_resume
from app.crew_engine import run_resume_analysis, run_career_roadmap, run_interview_simulator

# Logging configuration
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("Resume_AI_Main")

app = FastAPI(title="Enterprise Career & Resume AI Platform")

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database tables
@app.on_event("startup")
def on_startup():
    init_db()

# Mount auth routes
app.include_router(auth_router)

# --- Background CrewAI Thread Worker ---
def execute_crewai_analysis(report_id: int, resume_text: str, job_description: str, provider: str, api_key: str):
    logger.debug(f"[THREAD START] Starting execute_crewai_analysis for report_id: {report_id} using provider: {provider}")
    db_start = time.time()
    db: Session = next(get_db())
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        logger.error(f"[THREAD ERROR] Report with id {report_id} not found in DB.")
        return
    logger.debug(f"[DB READ] Report retrieved in {time.time() - db_start:.4f}s")
        
    try:
        logger.debug(f"[DB UPDATE] Setting status to RUNNING for report_id: {report_id}")
        db_start = time.time()
        report.status = "RUNNING"
        db.commit()
        logger.debug(f"[DB COMMIT] Status set to RUNNING in {time.time() - db_start:.4f}s")
        
        logger.debug(f"[CREWAI START] Initializing CrewAI and executing analysis for report_id: {report_id}")
        crew_start = time.time()
        results = run_resume_analysis(
            resume_text=resume_text,
            job_description=job_description,
            provider=provider,
            api_key=api_key
        )
        crew_duration = time.time() - crew_start
        logger.debug(f"[CREWAI COMPLETE] Analysis succeeded in {crew_duration:.4f}s")
        
        # Save results back to DB
        logger.debug(f"[DB UPDATE] Saving analysis results and setting status to COMPLETED for report_id: {report_id}")
        db_start = time.time()
        report.match_score = results["match_score"]
        report.parsed_profile = results["parsed_profile"]
        report.gap_analysis = results["gap_analysis"]
        report.suggestions = results["suggestions"]
        report.full_report = results["full_report"]
        report.status = "COMPLETED"
        db.commit()
        logger.debug(f"[DB COMMIT] Results saved, status COMPLETED in {time.time() - db_start:.4f}s")
        
    except Exception as e:
        error_detail = traceback.format_exc()
        logger.error(f"[THREAD EXCEPTION] CrewAI analysis failed for report_id {report_id} with error: {str(e)}\n{error_detail}")
        try:
            logger.debug(f"[DB UPDATE] Setting status to FAILED for report_id: {report_id}")
            db_start = time.time()
            report.status = "FAILED"
            report.error_message = f"{type(e).__name__}: {str(e)}"
            db.commit()
            logger.debug(f"[DB COMMIT] Status FAILED saved in {time.time() - db_start:.4f}s")
        except Exception as db_err:
            logger.error(f"[DB EXCEPTION] Failed to write failure status to DB: {str(db_err)}")

# --- Endpoints ---

# Schema for report response
class ReportResponse(BaseModel):
    id: int
    resume_id: int
    job_description: str
    match_score: Optional[int]
    status: str
    error_message: Optional[str]
    parsed_profile: Optional[str]
    gap_analysis: Optional[str]
    suggestions: Optional[str]
    full_report: Optional[str]
    created_at: str

    class Config:
        from_attributes = True

@app.post("/api/reports/analyze")
def start_analysis(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    job_description: str = Form(...),
    x_llm_provider: str = Header(default="gemini"),
    x_llm_key: Optional[str] = Header(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload resume, parse text, and trigger CrewAI background thread execution."""
    logger.debug("[REQUEST RECEIVED] POST /api/reports/analyze")
    logger.debug(f"[LLM PROVIDER] x-llm-provider: {x_llm_provider}")
    if not x_llm_key:
        logger.warning("[AUTH WARNING] LLM API key header (x-llm-key) is missing.")
        raise HTTPException(status_code=400, detail="LLM API key header is missing.")
    
    # 1. Read file and parse text
    logger.debug(f"[RESUME UPLOAD] Reading uploaded file: {file.filename}")
    upload_start = time.time()
    try:
        file_bytes = file.file.read()
        logger.debug(f"[RESUME UPLOAD] File read successfully ({len(file_bytes)} bytes) in {time.time() - upload_start:.4f}s")
        
        logger.debug(f"[RESUME PARSING START] Parsing content for {file.filename}")
        parse_start = time.time()
        resume_text = parse_resume(file.filename, file_bytes)
        logger.debug(f"[RESUME PARSING COMPLETE] Parsing finished in {time.time() - parse_start:.4f}s")
    except Exception as e:
        logger.error(f"[PARSING ERROR] Error parsing uploaded resume: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to parse upload resume: {str(e)}"
        )
        
    if not resume_text.strip():
        logger.warning("[PARSING WARNING] Extracted resume text content is empty.")
        raise HTTPException(status_code=400, detail="The uploaded resume text content is empty.")

    logger.debug(f"[JD UPLOAD] Job Description length: {len(job_description)} characters")

    # 2. Save resume entry
    logger.debug("[DB INSERT] Creating and saving Resume entry")
    db_start = time.time()
    resume = Resume(
        user_id=current_user.id,
        filename=file.filename,
        file_content_text=resume_text
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    logger.debug(f"[DB INSERT COMPLETE] Resume inserted (ID: {resume.id}) in {time.time() - db_start:.4f}s")

    # 3. Create initial pending report
    logger.debug("[DB INSERT] Creating and saving Report entry (status: PENDING)")
    db_start = time.time()
    report = Report(
        resume_id=resume.id,
        job_description=job_description,
        status="PENDING"
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    logger.debug(f"[DB INSERT COMPLETE] Report inserted (ID: {report.id}) in {time.time() - db_start:.4f}s")

    # 4. Delegate to background thread worker
    logger.debug("[BACKGROUND DELEGATION] Spawning execute_crewai_analysis thread")
    thread = threading.Thread(
        target=execute_crewai_analysis,
        kwargs={
            "report_id": report.id,
            "resume_text": resume_text,
            "job_description": job_description,
            "provider": x_llm_provider,
            "api_key": x_llm_key
        }
    )
    thread.start()

    # Convert to schema format
    logger.debug(f"[RESPONSE GENERATION] Returning success response for report_id: {report.id}")
    return {
        "id": report.id,
        "resume_id": report.resume_id,
        "job_description": report.job_description,
        "status": report.status,
        "created_at": report.created_at.isoformat()
    }

@app.get("/api/reports", response_model=List[ReportResponse])
def get_user_reports(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Retrieve all reports generated for the authenticated user's uploaded resumes."""
    reports = db.query(Report).join(Resume).filter(Resume.user_id == current_user.id).all()
    
    # Format and return list
    response_list = []
    for r in reports:
        response_list.append(ReportResponse(
            id=r.id,
            resume_id=r.resume_id,
            job_description=r.job_description,
            match_score=r.match_score,
            status=r.status,
            error_message=r.error_message,
            parsed_profile=r.parsed_profile,
            gap_analysis=r.gap_analysis,
            suggestions=r.suggestions,
            full_report=r.full_report,
            created_at=r.created_at.isoformat()
        ))
    return response_list

@app.get("/api/reports/{report_id}", response_model=ReportResponse)
def get_single_report(report_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Fetch status and complete output content of a specific analysis run."""
    report = db.query(Report).join(Resume).filter(
        Report.id == report_id,
        Resume.user_id == current_user.id
    ).first()
    
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")
        
    return ReportResponse(
        id=report.id,
        resume_id=report.resume_id,
        job_description=report.job_description,
        match_score=report.match_score,
        status=report.status,
        error_message=report.error_message,
        parsed_profile=report.parsed_profile,
        gap_analysis=report.gap_analysis,
        suggestions=report.suggestions,
        full_report=report.full_report,
        created_at=report.created_at.isoformat()
    )


# --- Career Hub & Learning Hub Endpoints ---

class RoadmapRequest(BaseModel):
    role_title: str
    target_industry: str
    current_skills: str

class InterviewRequest(BaseModel):
    role_title: str
    job_description: str

@app.post("/api/coaching/roadmap")
def build_roadmap(
    req: RoadmapRequest,
    x_llm_provider: str = Header(default="gemini"),
    x_llm_key: Optional[str] = Header(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Trigger Career Coach Agent to construct transition roadmaps."""
    if not x_llm_key:
        raise HTTPException(status_code=400, detail="LLM API key is required.")
        
    try:
        roadmap_content = run_career_roadmap(
            role_title=req.role_title,
            target_industry=req.target_industry,
            current_skills=req.current_skills,
            provider=x_llm_provider,
            api_key=x_llm_key
        )
        
        # Save activity log
        activity = CareerActivity(
            user_id=current_user.id,
            activity_type="ROADMAP",
            input_data=f"Target: {req.role_title} ({req.target_industry})",
            output_data=roadmap_content
        )
        db.add(activity)
        db.commit()
        
        return {
            "status": "success",
            "output_data": roadmap_content
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate roadmap: {str(e)}")

@app.post("/api/coaching/interview")
def simulate_interview(
    req: InterviewRequest,
    x_llm_provider: str = Header(default="gemini"),
    x_llm_key: Optional[str] = Header(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Trigger Technical Interview Agent to construct mock prep sheet."""
    if not x_llm_key:
        raise HTTPException(status_code=400, detail="LLM API key is required.")
        
    try:
        interview_sheet = run_interview_simulator(
            role_title=req.role_title,
            job_description=req.job_description,
            provider=x_llm_provider,
            api_key=x_llm_key
        )
        
        # Save activity log
        activity = CareerActivity(
            user_id=current_user.id,
            activity_type="INTERVIEW",
            input_data=f"Role: {req.role_title}",
            output_data=interview_sheet
        )
        db.add(activity)
        db.commit()
        
        return {
            "status": "success",
            "output_data": interview_sheet
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to simulate interview sheet: {str(e)}")


# --- Front-End Server Static Mounting ---

# Mounting the static folder
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/")
def read_root():
    """Default redirect to the static frontend SPA index file."""
    return RedirectResponse(url="/static/index.html")
