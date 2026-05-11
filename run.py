"""
run.py — Project entry point.
Starts FastAPI (uvicorn) + Streamlit in parallel processes.
"""
import subprocess, sys, os, time, signal

def run():
    os.makedirs("data/outputs", exist_ok=True)
    os.makedirs("data/resumes", exist_ok=True)
    os.makedirs("data/linkedin", exist_ok=True)
    os.makedirs("data/jd", exist_ok=True)
    os.makedirs("logs", exist_ok=True)

    from app.database.db import init_db
    init_db()

    api_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.api.main:app",
         "--host", "0.0.0.0", "--port", "8000", "--reload"],
        cwd=os.path.dirname(os.path.abspath(__file__)),
    )

    time.sleep(2)

    ui_proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app/ui/streamlit_app.py",
         "--server.port", "8501", "--server.address", "0.0.0.0"],
        cwd=os.path.dirname(os.path.abspath(__file__)),
    )

    print("\n" + "="*60)
    print("  HR Shortlisting Agent — RUNNING")
    print("="*60)
    print("  FastAPI Backend : http://localhost:8000")
    print("  API Docs        : http://localhost:8000/docs")
    print("  Streamlit UI    : http://localhost:8501")
    print("="*60)
    print("  Press Ctrl+C to stop both servers")
    print("="*60 + "\n")

    try:
        api_proc.wait()
    except KeyboardInterrupt:
        print("\nShutting down...")
        api_proc.terminate()
        ui_proc.terminate()
        sys.exit(0)

if __name__ == "__main__":
    run()
