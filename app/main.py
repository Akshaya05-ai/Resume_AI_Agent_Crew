import os
import threading
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
    db: Session = next(get_db())
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        return
        
    try:
        report.status = "RUNNING"
        db.commit()
        
        # Trigger the CrewAI orchestrator
        results = run_resume_analysis(
            resume_text=resume_text,
            job_description=job_description,
            provider=provider,
            api_key=api_key
        )
        
        # Save results back to DB
        report.match_score = results["match_score"]
        report.parsed_profile = results["parsed_profile"]
        report.gap_analysis = results["gap_analysis"]
        report.suggestions = results["suggestions"]
        report.full_report = results["full_report"]
        report.status = "COMPLETED"
        db.commit()
        
    except Exception as e:
        report.status = "FAILED"
        report.error_message = str(e)
        db.commit()
        print(f"Error in CrewAI Thread worker: {str(e)}")

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
    x_llm_provider: str = Header("gemini"),
    x_llm_key: str = Header(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload resume, parse text, and trigger CrewAI background thread execution."""
    if not x_llm_key:
        raise HTTPException(status_code=400, detail="LLM API key header is missing.")
        
    # 1. Read file and parse text
    try:
        file_bytes = file.file.read()
        resume_text = parse_resume(file.filename, file_bytes)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to parse upload resume: {str(e)}"
        )
        
    if not resume_text.strip():
        raise HTTPException(status_code=400, detail="The uploaded resume text content is empty.")

    # 2. Save resume entry
    resume = Resume(
        user_id=current_user.id,
        filename=file.filename,
        file_content_text=resume_text
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)

    # 3. Create initial pending report
    report = Report(
        resume_id=resume.id,
        job_description=job_description,
        status="PENDING"
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    # 4. Delegate to background thread worker
    # We use a standard python Thread so FastAPI returns immediately
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
    x_llm_provider: str = Header("gemini"),
    x_llm_key: str = Header(...),
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
    x_llm_provider: str = Header("gemini"),
    x_llm_key: str = Header(...),
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
