import os
import sys
from app.crew_engine import run_resume_analysis

def main():
    print("="*60)
    print("   CareerAI Multi-Agent Pipeline CLI Test Tool   ")
    print("="*60)

    # 1. Read files
    resume_path = "sample_resume.txt"
    jd_path = "sample_jd.txt"

    if not os.path.exists(resume_path) or not os.path.exists(jd_path):
        print("Error: sample_resume.txt and sample_jd.txt must be in the current directory.")
        sys.exit(1)

    with open(resume_path, "r", encoding="utf-8") as f:
        resume_text = f.read()

    with open(jd_path, "r", encoding="utf-8") as f:
        job_description = f.read()

    # 2. Get API Key
    provider = input("Select LLM Provider (gemini/openai) [default: gemini]: ").strip().lower() or "gemini"
    if provider not in ["gemini", "openai"]:
        print("Invalid provider selected.")
        sys.exit(1)

    env_var_name = "GEMINI_API_KEY" if provider == "gemini" else "OPENAI_API_KEY"
    api_key = os.environ.get(env_var_name, "").strip()

    if not api_key:
        api_key = input(f"Enter your {env_var_name}: ").strip()
        if not api_key:
            print("Error: API Key is required to run the multi-agent analysis.")
            sys.exit(1)

    print("\nStarting the 11-agent pipeline analysis...")
    print("This runs sequentially and may take 1-2 minutes. Please wait...\n")

    try:
        results = run_resume_analysis(
            resume_text=resume_text,
            job_description=job_description,
            provider=provider,
            api_key=api_key
        )
        
        print("\n" + "="*60)
        print(f" ANALYSIS COMPLETED SUCCESSFULLY - ATS MATCH: {results['match_score']}%")
        print("="*60 + "\n")

        # Save output to a report file
        output_report_file = "analysis_report_output.md"
        with open(output_report_file, "w", encoding="utf-8") as f:
            f.write(results["full_report"])

        print(f"The complete compiled report has been saved to: {output_report_file}")
        print("You can view it directly in markdown reader.")

    except Exception as e:
        print(f"\nPipeline run failed with error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
