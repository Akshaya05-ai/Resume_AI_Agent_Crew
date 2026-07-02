import sys
import os

def test_imports():
    print("Testing imports...")
    try:
        import fastapi
        import uvicorn
        import sqlalchemy
        import jose
        import pypdf
        import docx2txt
        import crewai
        print("Success: All core libraries imported correctly!")
    except ImportError as e:
        print(f"ImportError encountered: {e}")
        sys.exit(1)

def test_crew_compilation():
    print("Testing Crew compilation structures...")
    try:
        from app.crew_engine import run_resume_analysis
        print("Success: Crew Engine setup imported and compiled successfully!")
    except Exception as e:
        print(f"Crew Engine compilation error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_imports()
    # Since imports succeeded, we can test crew compilation directly
    test_crew_compilation()
    print("All checks completed.")
