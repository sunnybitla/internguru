import sqlite3
import os
import json

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.db")

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Profile table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS profile (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT,
        phone TEXT,
        linkedin_url TEXT,
        github_url TEXT,
        portfolio_url TEXT,
        resume_filename TEXT,
        resume_text TEXT,
        gemini_api_key TEXT,
        windows_daemon_enabled INTEGER DEFAULT 0,
        monday_time TEXT DEFAULT '09:00',
        dry_run INTEGER DEFAULT 1
    )
    """)
    
    # Migrate existing table if dry_run column is missing
    cursor.execute("PRAGMA table_info(profile)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'dry_run' not in columns:
        cursor.execute("ALTER TABLE profile ADD COLUMN dry_run INTEGER DEFAULT 1")
    
    # Insert default profile row if not exists
    cursor.execute("SELECT COUNT(*) FROM profile")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
        INSERT INTO profile (name, email, phone, linkedin_url, github_url, portfolio_url, resume_filename, resume_text, gemini_api_key, windows_daemon_enabled, monday_time, dry_run)
        VALUES ('', '', '', '', '', '', '', '', '', 0, '09:00', 1)
        """)

    # Jobs cache table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS jobs_cache (
        id TEXT PRIMARY KEY,
        title TEXT,
        company TEXT,
        company_logo TEXT,
        url TEXT,
        location TEXT,
        source TEXT,
        description TEXT,
        pub_date TEXT,
        is_internship INTEGER DEFAULT 0,
        fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Apply queue table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS apply_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT UNIQUE,
        cover_letter TEXT,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (job_id) REFERENCES jobs_cache(id) ON DELETE CASCADE
    )
    """)

    # Apply history table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS apply_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT,
        title TEXT,
        company TEXT,
        url TEXT,
        cover_letter TEXT,
        status TEXT, -- 'completed', 'failed', 'requires_manual'
        error_message TEXT,
        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()

# Profile Helpers
def get_profile():
    conn = get_db_connection()
    profile = conn.execute("SELECT * FROM profile WHERE id = 1").fetchone()
    conn.close()
    if profile:
        return dict(profile)
    return None

def update_profile(name, email, phone, linkedin_url, github_url, portfolio_url, resume_filename=None, resume_text=None, gemini_api_key=None, windows_daemon_enabled=None, monday_time=None, dry_run=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Dynamic update query
    updates = []
    params = []
    
    fields = {
        "name": name,
        "email": email,
        "phone": phone,
        "linkedin_url": linkedin_url,
        "github_url": github_url,
        "portfolio_url": portfolio_url,
        "resume_filename": resume_filename,
        "resume_text": resume_text,
        "gemini_api_key": gemini_api_key,
        "windows_daemon_enabled": windows_daemon_enabled,
        "monday_time": monday_time,
        "dry_run": dry_run
    }
    
    for k, v in fields.items():
        if v is not None:
            updates.append(f"{k} = ?")
            params.append(v)
            
    if updates:
        params.append(1) # ID = 1
        query = f"UPDATE profile SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, params)
        conn.commit()
    conn.close()

# Jobs Helpers
def save_jobs(jobs_list):
    conn = get_db_connection()
    cursor = conn.cursor()
    for job in jobs_list:
        cursor.execute("""
        INSERT INTO jobs_cache (id, title, company, company_logo, url, location, source, description, pub_date, is_internship)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            title=excluded.title,
            company=excluded.company,
            company_logo=excluded.company_logo,
            url=excluded.url,
            location=excluded.location,
            source=excluded.source,
            description=excluded.description,
            pub_date=excluded.pub_date,
            is_internship=excluded.is_internship
        """, (
            job['id'], job['title'], job['company'], job['company_logo'], job['url'], 
            job['location'], job['source'], job['description'], job['pub_date'], job['is_internship']
        ))
    conn.commit()
    conn.close()

def get_cached_jobs(limit=100, search="", is_internship=None):
    conn = get_db_connection()
    query = "SELECT * FROM jobs_cache WHERE 1=1"
    params = []
    
    if search:
        query += " AND (title LIKE ? OR company LIKE ? OR description LIKE ? OR location LIKE ?)"
        search_param = f"%{search}%"
        params.extend([search_param, search_param, search_param, search_param])
        
    if is_internship is not None:
        query += " AND is_internship = ?"
        params.append(1 if is_internship else 0)
        
    query += " ORDER BY pub_date DESC LIMIT ?"
    params.append(limit)
    
    jobs = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(j) for j in jobs]

def get_job_by_id(job_id):
    conn = get_db_connection()
    job = conn.execute("SELECT * FROM jobs_cache WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    return dict(job) if job else None

# Queue Helpers
def add_to_queue(job_id, cover_letter=""):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR REPLACE INTO apply_queue (job_id, cover_letter) VALUES (?, ?)", (job_id, cover_letter))
        conn.commit()
        success = True
    except Exception as e:
        print(f"Error adding to queue: {e}")
        success = False
    conn.close()
    return success

def remove_from_queue(job_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM apply_queue WHERE job_id = ?", (job_id,))
    conn.commit()
    conn.close()

def get_queue():
    conn = get_db_connection()
    query = """
    SELECT q.id as queue_id, q.job_id, q.cover_letter, q.added_at, j.*
    FROM apply_queue q
    JOIN jobs_cache j ON q.job_id = j.id
    ORDER BY q.added_at ASC
    """
    queue_items = conn.execute(query).fetchall()
    conn.close()
    return [dict(item) for item in queue_items]

def update_queue_cover_letter(job_id, cover_letter):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE apply_queue SET cover_letter = ? WHERE job_id = ?", (cover_letter, job_id))
    conn.commit()
    conn.close()

# History Helpers
def add_to_history(job_id, title, company, url, cover_letter, status, error_message=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO apply_history (job_id, title, company, url, cover_letter, status, error_message)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (job_id, title, company, url, cover_letter, status, error_message))
    
    # Once added to history, remove from the active queue
    cursor.execute("DELETE FROM apply_queue WHERE job_id = ?", (job_id,))
    
    conn.commit()
    conn.close()

def get_history():
    conn = get_db_connection()
    history = conn.execute("SELECT * FROM apply_history ORDER BY applied_at DESC").fetchall()
    conn.close()
    return [dict(item) for item in history]

def clear_history():
    conn = get_db_connection()
    conn.execute("DELETE FROM apply_history")
    conn.commit()
    conn.close()

# Initialize on import
init_db()
