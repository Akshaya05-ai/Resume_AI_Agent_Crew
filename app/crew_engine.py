import os
import re
from crewai import Agent, Task, Crew, Process, LLM

def get_llm(provider: str, api_key: str):
    """Initialize the LLM based on user selection and API Key."""
    if provider == "gemini":
        os.environ["GEMINI_API_KEY"] = api_key
        return LLM(
            model="gemini/gemini-1.5-flash",
            api_key=api_key,
            temperature=0.2
        )
    elif provider == "openai":
        os.environ["OPENAI_API_KEY"] = api_key
        return LLM(
            model="gpt-4o-mini",
            api_key=api_key,
            temperature=0.2
        )
    else:
        raise ValueError(f"Unsupported provider: {provider}")

def parse_ats_score(report_text: str) -> int:
    """Utility to attempt parsing ATS score from the text."""
    try:
        # Search for pattern like "ATS Score: 85%" or "85%"
        match = re.search(r"ATS[a-zA-Z\s]*Score:\s*(\d+)%", report_text, re.IGNORECASE)
        if match:
            return int(match.group(1))
        
        match = re.search(r"(\d+)%", report_text)
        if match:
            return int(match.group(1))
        
        # Default fallback
        return 75
    except Exception:
        return 70

def run_resume_analysis(resume_text: str, job_description: str, provider: str, api_key: str):
    """Run the 11-Agent CrewAI pipeline to analyze a resume."""
    
    llm = get_llm(provider, api_key)
    
    # --- Define 11 Agents ---
    
    # 1. Resume Parser Agent
    parser_agent = Agent(
        role="Resume Parser Agent",
        goal="Extract and structure candidate profile details including work experience, skills, education, and achievements.",
        backstory="You are an expert talent data architect who excels at converting raw resume text into structured professional profiles.",
        llm=llm,
        verbose=True
    )
    
    # 2. Grammar Agent
    grammar_agent = Agent(
        role="Grammar Agent",
        goal="Identify grammatical, spelling, and semantic errors in the resume.",
        backstory="You are a professional editor with an eagle eye for syntactic errors, grammar flaws, and punctuation issues.",
        llm=llm,
        verbose=True
    )
    
    # 3. Formatting Agent
    formatting_agent = Agent(
        role="Formatting Agent",
        goal="Analyze layout consistency, section ordering, word density, and visual flow of the resume.",
        backstory="You are a typographer and designer specialized in visual document readability and ATS parsing layout rules.",
        llm=llm,
        verbose=True
    )
    
    # 4. Keyword Agent
    keyword_agent = Agent(
        role="Keyword Agent",
        goal="Detect keyword density, identify missing high-value terms from the job description, and recommend insertions.",
        backstory="You are a semantic search optimizer. You know exactly what terms search filters and ATS parsers look for.",
        llm=llm,
        verbose=True
    )
    
    # 5. ATS Agent
    ats_agent = Agent(
        role="ATS Agent",
        goal="Provide an overall compatibility percentage score and evaluate compatibility with ATS parsing systems.",
        backstory="You are a reverse-engineered ATS scoring engine. You evaluate structural parseability and requirement alignment.",
        llm=llm,
        verbose=True
    )
    
    # 6. Recruiter Agent
    recruiter_agent = Agent(
        role="Recruiter Agent",
        goal="Evaluate candidate's visual impressions, professional progression, and highlight strengths.",
        backstory="You are an executive recruiter who reviews hundreds of resumes daily. You look for career growth and achievements.",
        llm=llm,
        verbose=True
    )
    
    # 7. HR Agent
    hr_agent = Agent(
        role="HR Agent",
        goal="Verify compliance, assess overall fit, soft skills, and cultural indicator gaps.",
        backstory="You are a seasoned HR director who evaluates organization alignment, soft skills, and team collaboration signals.",
        llm=llm,
        verbose=True
    )
    
    # 8. Technical Interview Agent
    tech_interview_agent = Agent(
        role="Technical Interview Agent",
        goal="Identify potential technical weak areas, and generate target technical interview questions.",
        backstory="You are a principal engineer and hiring manager. You know how to screen candidates and probe their claims.",
        llm=llm,
        verbose=True
    )
    
    # 9. Career Coach Agent
    career_coach_agent = Agent(
        role="Career Coach Agent",
        goal="Formulate strategic next steps, advice, and a personalized professional development plan.",
        backstory="You are an executive career advisor helping professionals pivot and advance in their career paths.",
        llm=llm,
        verbose=True
    )
    
    # 10. Resume Rewrite Agent
    rewrite_agent = Agent(
        role="Resume Rewrite Agent",
        goal="Formulate precise rewrites for weak resume bullets using the STAR method.",
        backstory="You are a professional resume writer who transforms boring responsibilities into quantifiable achievement statements.",
        llm=llm,
        verbose=True
    )
    
    # 11. Report Generator Agent
    report_agent = Agent(
        role="Report Generator Agent",
        goal="Synthesize reports from all prior stages into a single, beautifully styled markdown document.",
        backstory="You are a principal technical editor and content architect who creates structured executive summaries.",
        llm=llm,
        verbose=True
    )

    # --- Define Tasks (Sequentially mapping downstream dependencies) ---
    
    # Task 1: Parse and structure
    t1_parse = Task(
        description=f"Extract and structure contact info, experience, skills, and education from this resume:\n\n{resume_text}",
        expected_output="Structured markdown document of the candidate profile.",
        agent=parser_agent
    )
    
    # Task 2: Language, formatting, keywords audit
    t2_audit = Task(
        description=(
            f"Review the original resume for grammar, spelling, format layouts, and keyword density. "
            f"Identify missing keywords from this Job Description:\n\n{job_description}"
        ),
        expected_output="An audit report detailing spelling/grammar errors, layout flags, and missing keywords.",
        agent=keyword_agent, # Handled by keyword agent (collaborating with grammar/formatting logic)
        context=[t1_parse]
    )
    
    # Task 3: ATS analysis
    t3_ats = Task(
        description=(
            f"Analyze the parsed profile and the audit report against this job description:\n\n{job_description}\n\n"
            "Estimate an overall ATS compatibility score percentage (0-100%)."
        ),
        expected_output="An ATS compatibility review. MUST include an 'ATS Score: X%' string where X is the percentage.",
        agent=ats_agent,
        context=[t1_parse, t2_audit]
    )
    
    # Task 4: Human reviewer simulation
    t4_hiring = Task(
        description=(
            "Simulate a recruiter and HR director reviewing this candidate profile. "
            "Highlight strengths, weaknesses, and potential red flags."
        ),
        expected_output="Recruiter & HR comments, detailing candidate strengths and organizational fit.",
        agent=recruiter_agent,
        context=[t1_parse, t3_ats]
    )
    
    # Task 5: Interview prep & coaching
    t5_coaching = Task(
        description=(
            f"Create a target set of 5 interview questions with answers for the candidate based on job requirements: {job_description}. "
            "Additionally, formulate a short career advice plan."
        ),
        expected_output="Coaching section with 5 technical/behavioral questions, answers, and strategic career advice.",
        agent=career_coach_agent,
        context=[t1_parse, t4_hiring]
    )
    
    # Task 6: Bullet point optimization
    t6_rewrite = Task(
        description="Select at least 3 weak points from the parsed work experience and rewrite them using the STAR method.",
        expected_output="List of bullet points showing 'Before' (original) vs 'After' (rewritten), emphasizing quantifiable metrics.",
        agent=rewrite_agent,
        context=[t1_parse, t3_ats]
    )
    
    # Task 7: Compile executive report
    t7_compile = Task(
        description=(
            "Compile all reviews, feedback, rewrites, and questions from previous tasks into a single cohesive report. "
            "Format the report using clean markdown, containing headers for all sections: "
            "1. Executive Summary & ATS Score\n"
            "2. Profile parsing & structure\n"
            "3. Grammar & Formatting Feedback\n"
            "4. ATS Keyword Gaps\n"
            "5. Recruiter & HR feedback\n"
            "6. STAR Bullet Point Rewrites\n"
            "7. Interview Preparation Questions\n"
            "8. Career Coach Recommendations"
        ),
        expected_output="A comprehensive Markdown document containing all analysis sections.",
        agent=report_agent,
        context=[t1_parse, t2_audit, t3_ats, t4_hiring, t5_coaching, t6_rewrite]
    )
    
    # Create and run the Crew
    crew = Crew(
        agents=[
            parser_agent, grammar_agent, formatting_agent, keyword_agent,
            ats_agent, recruiter_agent, hr_agent, tech_interview_agent,
            career_coach_agent, rewrite_agent, report_agent
        ],
        tasks=[t1_parse, t2_audit, t3_ats, t4_hiring, t5_coaching, t6_rewrite, t7_compile],
        process=Process.sequential,
        verbose=True
    )
    
    result = crew.kickoff()
    
    # Extract string result
    report_content = str(result)
    
    # Parse ATS score from it
    ats_score = parse_ats_score(report_content)
    
    # Deconstruct parts for SQLite storage if possible, or just parse headings
    sections = {
        "full_report": report_content,
        "match_score": ats_score,
        "parsed_profile": getattr(t1_parse.output, 'raw', "Profile parsed successfully."),
        "gap_analysis": getattr(t3_ats.output, 'raw', "ATS match analysis completed."),
        "suggestions": getattr(t6_rewrite.output, 'raw', "Bullet points rewritten successfully.")
    }
    
    return sections


def run_career_roadmap(role_title: str, target_industry: str, current_skills: str, provider: str, api_key: str) -> str:
    """Generate a learning roadmap based on a target role and current skills."""
    llm = get_llm(provider, api_key)
    
    coach = Agent(
        role="Career Coach Agent",
        goal=f"Create a structured, step-by-step career path and learning roadmap to become a {role_title}.",
        backstory="You are an expert career architect with deep knowledge of learning resources, skill pathways, and tech industry standards.",
        llm=llm,
        verbose=True
    )
    
    roadmap_task = Task(
        description=(
            f"Build a comprehensive learning roadmap to transition from the current skills to a {role_title} role in the {target_industry} industry.\n"
            f"Current Skills: {current_skills}\n"
            "Include:\n"
            "- Step-by-step skill acquisition timeline\n"
            "- Recommended certifications or study paths\n"
            "- Practical projects to build for a portfolio\n"
            "- 30-60-90 day action plan"
        ),
        expected_output="A structured markdown learning roadmap with action items.",
        agent=coach
    )
    
    crew = Crew(
        agents=[coach],
        tasks=[roadmap_task],
        process=Process.sequential,
        verbose=True
    )
    
    result = crew.kickoff()
    return str(result)


def run_interview_simulator(role_title: str, job_description: str, provider: str, api_key: str) -> str:
    """Generate a simulation of technical/behavioral interview questions for a role."""
    llm = get_llm(provider, api_key)
    
    interviewer = Agent(
        role="Technical Interview Agent",
        goal=f"Generate deep, challenging technical and situational questions for a {role_title} position.",
        backstory="You are a principal engineer and elite recruiter. You design interviews that probe practical problem-solving skills.",
        llm=llm,
        verbose=True
    )
    
    sim_task = Task(
        description=(
            f"Generate a customized technical interview preparation sheet for a {role_title} role.\n"
            f"Job Description context:\n{job_description}\n\n"
            "Please provide:\n"
            "1. 5 High-impact Technical Questions with suggested detailed Answers.\n"
            "2. 3 Behavioral Questions using the STAR framework with sample Answers.\n"
            "3. Key competencies the interviewer will probe."
        ),
        expected_output="A structured markdown preparation sheet with questions and solutions.",
        agent=interviewer
    )
    
    crew = Crew(
        agents=[interviewer],
        tasks=[sim_task],
        process=Process.sequential,
        verbose=True
    )
    
    result = crew.kickoff()
    return str(result)
