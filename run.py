import os
import sys
import subprocess

def run_cmd(command):
    """Run a system command and print output in real-time."""
    print(f"Executing: {command}")
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in process.stdout:
        print(line, end="")
    process.wait()
    return process.returncode

def main():
    print("="*60)
    print("   CareerAI Enterprise Platform Startup script   ")
    print("="*60)

    # 1. Locate/Create Virtual Environment
    venv_dir = ".venv"
    pip_path = os.path.join(venv_dir, "Scripts", "pip") if os.name == "nt" else os.path.join(venv_dir, "bin", "pip")
    python_path = os.path.join(venv_dir, "Scripts", "python") if os.name == "nt" else os.path.join(venv_dir, "bin", "python")

    if not os.path.exists(venv_dir):
        print(f"Creating python virtual environment at {venv_dir}...")
        ret = run_cmd(f"{sys.executable} -m venv {venv_dir}")
        if ret != 0:
            print("Failed to create virtual environment.")
            sys.exit(1)
    else:
        print("Virtual environment already exists.")

    # 2. Check and Install Requirements
    print("Installing/verifying required python libraries from requirements.txt...")
    ret = run_cmd(f"{pip_path} install -r requirements.txt")
    if ret != 0:
        print("Failed to install dependencies.")
        sys.exit(1)

    # 3. Rerun installation specifically for python-jose[cryptography] in case of issues
    print("Ensuring JWT cryptographic library is fully configured...")
    run_cmd(f"{pip_path} install \"python-jose[cryptography]\"")

    # 4. Launch FastAPI Uvicorn Server
    print("Starting FastAPI Uvicorn developer server...")
    uvicorn_cmd = f"{python_path} -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
    
    try:
        run_cmd(uvicorn_cmd)
    except KeyboardInterrupt:
        print("\nStopping CareerAI server. Goodbye!")

if __name__ == "__main__":
    main()
