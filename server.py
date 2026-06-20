import os
import subprocess
import shutil
import platform
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import database
import scraper
import parser
import applier

app = FastAPI(title="AI Job Applier Agent")

# Process-level scheduler
scheduler = BackgroundScheduler()

def run_monday_apply():
    print("Process-level scheduler running Monday Apply...")
    applier.run_auto_apply_queue()

def update_process_scheduler():
    """
    Updates the process-level cron job based on settings in the DB.
    """
    profile = database.get_profile()
    if not profile:
        return
        
    # Remove existing job if it exists
    if scheduler.get_job('monday_apply'):
        scheduler.remove_job('monday_apply')
        
    time_str = profile.get('monday_time', '09:00')
    try:
        hour, minute = map(int, time_str.split(':'))
        scheduler.add_job(
            run_monday_apply,
            CronTrigger(day_of_week='mon', hour=hour, minute=minute),
            id='monday_apply'
        )
        print(f"Process scheduler set for Monday at {hour:02d}:{minute:02d}")
    except Exception as e:
        print(f"Error setting process scheduler: {e}")

@app.on_event("startup")
def startup_event():
    database.init_db()
    scheduler.start()
    update_process_scheduler()
    # Pre-sync jobs on startup in a background thread to prevent blocking server startup
    import threading
    def background_sync():
        try:
            print("Background startup job sync starting...")
            count = scraper.sync_jobs()
            print(f"Background startup job sync completed. Synced {count} jobs.")
        except Exception as e:
            print(f"Background startup job sync failed: {e}")
            
    threading.Thread(target=background_sync, daemon=True).start()

@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown()

# Models
class QueueItem(BaseModel):
    job_id: str
    cover_letter: Optional[str] = ""

class UpdateCoverLetterRequest(BaseModel):
    cover_letter: str

class DaemonToggle(BaseModel):
    enabled: bool

class DryRunToggle(BaseModel):
    enabled: bool

# API Routes
@app.get("/api/profile")
def get_profile_api():
    profile = database.get_profile()
    if profile:
        # Mask Gemini API Key for security
        p_dict = dict(profile)
        if p_dict.get('gemini_api_key'):
            p_dict['gemini_api_key'] = "sk-..." + p_dict['gemini_api_key'][-4:] if len(p_dict['gemini_api_key']) > 4 else "sk-..."
        return p_dict
    return {}

@app.post("/api/profile")
async def update_profile_api(
    name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    linkedin_url: str = Form(""),
    github_url: str = Form(""),
    portfolio_url: str = Form(""),
    gemini_api_key: str = Form(""),
    monday_time: str = Form("09:00"),
    resume: Optional[UploadFile] = File(None)
):
    profile = database.get_profile()
    current_key = profile.get('gemini_api_key', '') if profile else ''
    
    # If the user submitted a masked key, don't overwrite the actual key
    api_key_to_save = gemini_api_key
    if gemini_api_key.startswith("sk-..."):
        api_key_to_save = current_key

    resume_filename = None
    resume_text = None
    
    if resume and resume.filename:
        # Save resume file locally
        file_ext = os.path.splitext(resume.filename)[1]
        if file_ext.lower() != '.pdf':
            raise HTTPException(status_code=400, detail="Only PDF resumes are supported.")
            
        saved_name = "resume.pdf"
        data_dir = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
        target_path = os.path.join(data_dir, saved_name)
        
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(resume.file, buffer)
            
        resume_filename = saved_name
        
        # Parse the resume
        parsed = parser.parse_resume_pdf(target_path)
        if parsed.get('success'):
            resume_text = parsed.get('text')
            
    database.update_profile(
        name=name,
        email=email,
        phone=phone,
        linkedin_url=linkedin_url,
        github_url=github_url,
        portfolio_url=portfolio_url,
        resume_filename=resume_filename,
        resume_text=resume_text,
        gemini_api_key=api_key_to_save,
        monday_time=monday_time
    )
    
    update_process_scheduler()
    return {"status": "success", "message": "Profile updated successfully"}

@app.get("/api/jobs")
def get_jobs(search: Optional[str] = "", internship: Optional[bool] = None, sync: Optional[bool] = False):
    if sync:
        try:
            new_count = scraper.sync_jobs()
            print(f"Synced {new_count} jobs from APIs.")
        except Exception as e:
            print(f"Sync error: {e}")
            
    jobs = database.get_cached_jobs(limit=100, search=search, is_internship=internship)
    return jobs

@app.get("/api/queue")
def get_queue_api():
    return database.get_queue()

@app.post("/api/queue")
def add_to_queue_api(item: QueueItem):
    job = database.get_job_by_id(item.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found in cache.")
        
    profile = database.get_profile()
    
    # Generate cover letter if none provided
    cover_letter = item.cover_letter
    if not cover_letter:
        cover_letter = applier.generate_cover_letter(profile, job['title'], job['company'], job['description'])
        
    success = database.add_to_queue(item.job_id, cover_letter)
    if success:
        return {"status": "success", "cover_letter": cover_letter}
    else:
        raise HTTPException(status_code=500, detail="Failed to add to queue.")

@app.post("/api/queue/{job_id}/cover-letter")
def update_cover_letter(job_id: str, request: UpdateCoverLetterRequest):
    database.update_queue_cover_letter(job_id, request.cover_letter)
    return {"status": "success"}

@app.delete("/api/queue/{job_id}")
def remove_from_queue_api(job_id: str):
    database.remove_from_queue(job_id)
    return {"status": "success"}

@app.get("/api/history")
def get_history_api():
    return database.get_history()

@app.post("/api/history/clear")
def clear_history_api():
    database.clear_history()
    return {"status": "success"}

@app.post("/api/trigger-run")
def trigger_run_api():
    applied = applier.run_auto_apply_queue()
    return {"status": "success", "applied": applied}

@app.post("/api/toggle-dry-run")
def toggle_dry_run_api(toggle: DryRunToggle):
    try:
        database.update_profile(
            name=None, email=None, phone=None, linkedin_url=None, github_url=None, portfolio_url=None,
            dry_run=1 if toggle.enabled else 0
        )
        return {"status": "success", "message": f"Dry Run mode {'enabled' if toggle.enabled else 'disabled'} successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update Dry Run setting: {str(e)}")

@app.post("/api/toggle-daemon")
def toggle_daemon_api(toggle: DaemonToggle):
    if platform.system() != 'Windows':
        raise HTTPException(
            status_code=400, 
            detail="Windows Task Scheduler is only supported on Windows. On cloud/Linux deployments, the process-level background scheduler will run automatically while the server is active."
        )
        
    profile = database.get_profile()
    if not profile:
        raise HTTPException(status_code=400, detail="Profile not configured")
        
    time_str = profile.get('monday_time', '09:00')
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scheduler_daemon.py")
    venv_python = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv", "Scripts", "python.exe")
    
    task_name = "AI_Job_Applier"
    
    if toggle.enabled:
        # Check if venv python exists
        if not os.path.exists(venv_python):
            # Fall back to system python if venv python doesn't exist yet (though it should)
            venv_python = "python"
            
        command = f'schtasks /create /tn "{task_name}" /tr "\'{venv_python}\' \'{script_path}\'" /sc weekly /d MON /st {time_str} /f'
        try:
            # Run schtasks via PowerShell/CMD
            result = subprocess.run(["powershell", "-Command", command], capture_output=True, text=True, check=True)
            database.update_profile(name=None, email=None, phone=None, linkedin_url=None, github_url=None, portfolio_url=None, windows_daemon_enabled=1)
            return {"status": "success", "message": "Windows Task Scheduled successfully", "output": result.stdout}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to register Windows Scheduled Task: {str(e)}")
    else:
        command = f'schtasks /delete /tn "{task_name}" /f'
        try:
            result = subprocess.run(["powershell", "-Command", command], capture_output=True, text=True)
            database.update_profile(name=None, email=None, phone=None, linkedin_url=None, github_url=None, portfolio_url=None, windows_daemon_enabled=0)
            return {"status": "success", "message": "Windows Task unregistered successfully", "output": result.stdout}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to unregister Windows Scheduled Task: {str(e)}")

# Serve frontend static files
frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")
if not os.path.exists(frontend_dir):
    os.makedirs(frontend_dir)

# Catch-all route to serve the dashboard SPA
@app.get("/")
def read_root():
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return JSONResponse({"message": "Frontend not found. Please place files in frontend/ directory."})

app.mount("/", StaticFiles(directory=frontend_dir), name="static")
