import os
import subprocess
import shutil
import platform
import hmac
import hashlib
import base64
import time
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import database
import scraper
import parser
import applier
import requests

app = FastAPI(title="AI Job Applier Agent")

SECRET_KEY = "super-secret-key-job-agent"
security = HTTPBearer()

def create_token(user_id: int) -> str:
    timestamp = int(time.time())
    payload = f"{user_id}:{timestamp}"
    signature = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    token = base64.b64encode(f"{payload}:{signature}".encode()).decode()
    return token

def verify_token(token: str) -> Optional[int]:
    try:
        decoded = base64.b64decode(token.encode()).decode()
        parts = decoded.split(':')
        if len(parts) != 3:
            return None
        user_id_str, timestamp_str, signature = parts
        user_id = int(user_id_str)
        timestamp = int(timestamp_str)
        
        if time.time() - timestamp > 7 * 24 * 3600:
            return None
            
        expected_sig = hmac.new(SECRET_KEY.encode(), f"{user_id_str}:{timestamp_str}".encode(), hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected_sig, signature):
            return user_id
    except Exception:
        return None
    return None

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    user_id = verify_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token or session expired.")
    user = database.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found.")
    return user

# Process-level scheduler
scheduler = BackgroundScheduler()

def run_monday_apply():
    print("Process-level scheduler running Monday Apply...")
    applier.run_auto_apply_queue()

def update_process_scheduler(user_id=1):
    """
    Updates the process-level cron job based on settings in the DB.
    """
    profile = database.get_profile(user_id)
    if not profile:
        return
        
    job_name = f'monday_apply_{user_id}'
    # Remove existing job if it exists
    if scheduler.get_job(job_name):
        scheduler.remove_job(job_name)
        
    time_str = profile.get('monday_time', '09:00')
    try:
        hour, minute = map(int, time_str.split(':'))
        scheduler.add_job(
            lambda: applier.run_auto_apply_queue(user_id),
            CronTrigger(day_of_week='mon', hour=hour, minute=minute),
            id=job_name
        )
        print(f"Process scheduler for user {user_id} set for Monday at {hour:02d}:{minute:02d}")
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

class AuthRequest(BaseModel):
    username: str
    password: str

class GoogleAuthRequest(BaseModel):
    credential: str

@app.get("/api/auth/config")
def get_auth_config():
    return {
        "google_client_id": os.getenv("GOOGLE_CLIENT_ID", "100000000000-placeholder.apps.googleusercontent.com")
    }

@app.post("/api/auth/register")
def register(req: AuthRequest):
    if len(req.username.strip()) < 3 or len(req.password.strip()) < 4:
        raise HTTPException(status_code=400, detail="Username must be >= 3 characters, password >= 4 characters.")
    
    existing = database.get_user_by_username(req.username)
    if existing:
        raise HTTPException(status_code=400, detail="Username is already taken.")
        
    success, user_id = database.create_user(req.username, req.password)
    if success:
        token = create_token(user_id)
        return {"status": "success", "token": token, "username": req.username}
    else:
        raise HTTPException(status_code=500, detail="Failed to create user account.")

@app.post("/api/auth/login")
def login(req: AuthRequest):
    user = database.authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid username or password.")
        
    token = create_token(user['id'])
    return {"status": "success", "token": token, "username": req.username}

@app.post("/api/auth/google")
def google_auth(req: GoogleAuthRequest):
    # Call Google's tokeninfo API to verify the ID Token
    tokeninfo_url = f"https://oauth2.googleapis.com/tokeninfo?id_token={req.credential}"
    try:
        response = requests.get(tokeninfo_url, timeout=10)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reach Google verification server: {str(e)}")
        
    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Invalid Google credential token.")
        
    token_data = response.json()
    
    # Verify the audience (client_id) if configured
    google_client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    if google_client_id:
        token_aud = token_data.get("aud", "")
        if token_aud != google_client_id:
            raise HTTPException(status_code=400, detail="Google token client ID mismatch.")
            
    # Extract user details
    google_id = token_data.get("sub")
    email = token_data.get("email", "")
    name = token_data.get("name", "")
    
    if not google_id:
        raise HTTPException(status_code=400, detail="Google authentication failed (sub missing).")
        
    # Pattern for Google user: "google:{sub}"
    username = f"google:{google_id}"
    user = database.get_user_by_username(username)
    
    if not user:
        # Generate a random password not used for logins
        import secrets
        random_password = secrets.token_hex(16)
        success, user_id = database.create_user(username, random_password)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to create user account for Google profile.")
            
        # Initialize profile with Google details
        database.update_profile(
            user_id=user_id,
            name=name,
            email=email,
            phone="",
            linkedin_url="",
            github_url="",
            portfolio_url=""
        )
    else:
        user_id = user['id']
        
    # Generate app JWT session token
    token = create_token(user_id)
    return {"status": "success", "token": token, "username": username}

# API Routes
@app.get("/api/profile")
def get_profile_api(current_user = Depends(get_current_user)):
    user_id = current_user['id']
    profile = database.get_profile(user_id)
    if profile:
        # Mask API Keys for security
        p_dict = dict(profile)
        if p_dict.get('gemini_api_key'):
            p_dict['gemini_api_key'] = "sk-..." + p_dict['gemini_api_key'][-4:] if len(p_dict['gemini_api_key']) > 4 else "sk-..."
        if p_dict.get('linkedin_api_key'):
            p_dict['linkedin_api_key'] = "ln-..." + p_dict['linkedin_api_key'][-4:] if len(p_dict['linkedin_api_key']) > 4 else "ln-..."
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
    linkedin_api_key: str = Form(""),
    monday_time: str = Form("09:00"),
    resume: Optional[UploadFile] = File(None),
    current_user = Depends(get_current_user)
):
    user_id = current_user['id']
    profile = database.get_profile(user_id)
    current_key = profile.get('gemini_api_key', '') if profile else ''
    current_linkedin_key = profile.get('linkedin_api_key', '') if profile else ''
    
    # If the user submitted a masked key, don't overwrite the actual key
    api_key_to_save = gemini_api_key
    if gemini_api_key.startswith("sk-..."):
        api_key_to_save = current_key

    linkedin_key_to_save = linkedin_api_key
    if linkedin_api_key.startswith("ln-..."):
        linkedin_key_to_save = current_linkedin_key

    resume_filename = profile.get('resume_filename') if profile else None
    resume_text = profile.get('resume_text') if profile else None
    
    if resume and resume.filename:
        # Save resume file locally
        file_ext = os.path.splitext(resume.filename)[1]
        if file_ext.lower() != '.pdf':
            raise HTTPException(status_code=400, detail="Only PDF resumes are supported.")
            
        saved_name = f"resume_{user_id}.pdf"
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
        user_id=user_id,
        name=name,
        email=email,
        phone=phone,
        linkedin_url=linkedin_url,
        github_url=github_url,
        portfolio_url=portfolio_url,
        resume_filename=resume_filename,
        resume_text=resume_text,
        gemini_api_key=api_key_to_save,
        linkedin_api_key=linkedin_key_to_save,
        monday_time=monday_time
    )
    
    update_process_scheduler(user_id)
    return {"status": "success", "message": "Profile updated successfully"}

@app.get("/api/jobs")
def get_jobs(search: Optional[str] = "", internship: Optional[bool] = None, sync: Optional[bool] = False, current_user = Depends(get_current_user)):
    if sync:
        try:
            new_count = scraper.sync_jobs()
            print(f"Synced {new_count} jobs from APIs.")
        except Exception as e:
            print(f"Sync error: {e}")
            
    jobs = database.get_cached_jobs(limit=100, search=search, is_internship=internship)
    return jobs

@app.get("/api/queue")
def get_queue_api(current_user = Depends(get_current_user)):
    return database.get_queue(current_user['id'])

@app.post("/api/queue")
def add_to_queue_api(item: QueueItem, current_user = Depends(get_current_user)):
    user_id = current_user['id']
    job = database.get_job_by_id(item.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found in cache.")
        
    profile = database.get_profile(user_id)
    
    # 1. Resolve LinkedIn job details lazily if this is a LinkedIn job
    if job['url'].startswith("https://www.linkedin.com/") or job['url'].startswith("https://linkedin.com/") or "linkedin_" in job['id']:
        print(f"Resolving LinkedIn job details lazily for {job['id']}...")
        resolved_url, resolved_desc = scraper.resolve_linkedin_job(job['id'])
        if resolved_url or resolved_desc:
            updated_url = resolved_url or job['url']
            updated_desc = resolved_desc or job['description']
            database.update_job_details(job['id'], updated_url, updated_desc)
            # Update local variables for cover letter generation and queueing
            job['url'] = updated_url
            job['description'] = updated_desc
            print(f"Successfully resolved LinkedIn job details. New URL: {updated_url}")
    
    # Generate cover letter if none provided
    cover_letter = item.cover_letter
    if not cover_letter:
        cover_letter = applier.generate_cover_letter(profile, job['title'], job['company'], job['description'])
        
    success = database.add_to_queue(user_id, item.job_id, cover_letter)
    if success:
        return {"status": "success", "cover_letter": cover_letter}
    else:
        raise HTTPException(status_code=500, detail="Failed to add to queue.")

@app.post("/api/queue/{job_id}/cover-letter")
def update_cover_letter(job_id: str, request: UpdateCoverLetterRequest, current_user = Depends(get_current_user)):
    database.update_queue_cover_letter(current_user['id'], job_id, request.cover_letter)
    return {"status": "success"}

@app.delete("/api/queue/{job_id}")
def remove_from_queue_api(job_id: str, current_user = Depends(get_current_user)):
    database.remove_from_queue(current_user['id'], job_id)
    return {"status": "success"}

@app.get("/api/history")
def get_history_api(current_user = Depends(get_current_user)):
    return database.get_history(current_user['id'])

@app.post("/api/history/clear")
def clear_history_api(current_user = Depends(get_current_user)):
    database.clear_history(current_user['id'])
    return {"status": "success"}

@app.post("/api/trigger-run")
def trigger_run_api(current_user = Depends(get_current_user)):
    applied = applier.run_auto_apply_queue(current_user['id'])
    return {"status": "success", "applied": applied}

@app.post("/api/toggle-dry-run")
def toggle_dry_run_api(toggle: DryRunToggle, current_user = Depends(get_current_user)):
    user_id = current_user['id']
    try:
        database.update_profile(
            user_id=user_id,
            name=None, email=None, phone=None, linkedin_url=None, github_url=None, portfolio_url=None,
            dry_run=1 if toggle.enabled else 0
        )
        return {"status": "success", "message": f"Dry Run mode {'enabled' if toggle.enabled else 'disabled'} successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update Dry Run setting: {str(e)}")

@app.post("/api/toggle-daemon")
def toggle_daemon_api(toggle: DaemonToggle, current_user = Depends(get_current_user)):
    user_id = current_user['id']
    profile = database.get_profile(user_id)
    if not profile:
        raise HTTPException(status_code=400, detail="Profile not configured")
        
    time_str = profile.get('monday_time', '09:00')
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scheduler_daemon.py")
    venv_python = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv", "Scripts", "python.exe")
    
    task_name = f"AI_Job_Applier_{user_id}"
    
    if toggle.enabled:
        # Check if venv python exists
        if not os.path.exists(venv_python):
            # Fall back to system python if venv python doesn't exist yet (though it should)
            venv_python = "python"
            
        cmd = [
            "schtasks", "/create",
            "/tn", task_name,
            "/tr", f"'{venv_python}' '{script_path}' {user_id}",
            "/sc", "weekly",
            "/d", "MON",
            "/st", time_str,
            "/f"
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            database.update_profile(user_id=user_id, name=None, email=None, phone=None, linkedin_url=None, github_url=None, portfolio_url=None, windows_daemon_enabled=1)
            return {"status": "success", "message": "Windows Task Scheduled successfully", "output": result.stdout}
        except FileNotFoundError:
            raise HTTPException(
                status_code=400,
                detail="Windows Task Scheduler (schtasks) is not available on this platform. On cloud/Linux/Docker deployments, the process-level background scheduler will run automatically while the server is active."
            )
        except Exception as e:
            # Retrieve stderr for richer error reports
            error_msg = str(e)
            if hasattr(e, 'stderr') and e.stderr:
                error_msg += f" (stderr: {e.stderr})"
            raise HTTPException(status_code=500, detail=f"Failed to register Windows Scheduled Task: {error_msg}")
    else:
        cmd = ["schtasks", "/delete", "/tn", task_name, "/f"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            database.update_profile(user_id=user_id, name=None, email=None, phone=None, linkedin_url=None, github_url=None, portfolio_url=None, windows_daemon_enabled=0)
            return {"status": "success", "message": "Windows Task unregistered successfully", "output": result.stdout}
        except FileNotFoundError:
            raise HTTPException(
                status_code=400,
                detail="Windows Task Scheduler (schtasks) is not available on this platform."
            )
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
