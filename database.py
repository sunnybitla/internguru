import sqlite3
import os
import json

DATA_DIR = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
os.makedirs(DATA_DIR, exist_ok=True)
DB_FILE = os.path.join(DATA_DIR, "data.db")

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password_hash TEXT,
        salt TEXT
    )
    """)

    # Profile table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS profile (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE,
        name TEXT,
        email TEXT,
        phone TEXT,
        linkedin_url TEXT,
        github_url TEXT,
        portfolio_url TEXT,
        resume_filename TEXT,
        resume_text TEXT,
        gemini_api_key TEXT,
        linkedin_api_key TEXT DEFAULT '',
        windows_daemon_enabled INTEGER DEFAULT 0,
        monday_time TEXT DEFAULT '09:00',
        dry_run INTEGER DEFAULT 1,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)
    
    # Migrate existing table if columns are missing
    cursor.execute("PRAGMA table_info(profile)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'dry_run' not in columns:
        cursor.execute("ALTER TABLE profile ADD COLUMN dry_run INTEGER DEFAULT 1")
    if 'linkedin_api_key' not in columns:
        cursor.execute("ALTER TABLE profile ADD COLUMN linkedin_api_key TEXT DEFAULT ''")
    if 'user_id' not in columns:
        cursor.execute("ALTER TABLE profile ADD COLUMN user_id INTEGER")
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_profile_user_id ON profile(user_id)")
        cursor.execute("UPDATE profile SET user_id = 1 WHERE user_id IS NULL")

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
    cursor.execute("PRAGMA table_info(apply_queue)")
    q_info = cursor.fetchall()
    q_columns = [col[1] for col in q_info] if q_info else []
    if not q_columns or 'user_id' not in q_columns:
        cursor.execute("DROP TABLE IF EXISTS apply_queue")
        cursor.execute("""
        CREATE TABLE apply_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            job_id TEXT,
            cover_letter TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, job_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (job_id) REFERENCES jobs_cache(id) ON DELETE CASCADE
        )
        """)
    else:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS apply_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            job_id TEXT,
            cover_letter TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, job_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (job_id) REFERENCES jobs_cache(id) ON DELETE CASCADE
        )
        """)

    # Apply history table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS apply_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        job_id TEXT,
        title TEXT,
        company TEXT,
        url TEXT,
        cover_letter TEXT,
        status TEXT, -- 'completed', 'failed', 'requires_manual'
        error_message TEXT,
        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)
    cursor.execute("PRAGMA table_info(apply_history)")
    h_columns = [col[1] for col in cursor.fetchall()]
    if 'user_id' not in h_columns:
        cursor.execute("ALTER TABLE apply_history ADD COLUMN user_id INTEGER DEFAULT 1")

    # Insert default admin user if no users exist
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        import hashlib
        import os
        salt = os.urandom(16).hex()
        password_hash = hashlib.sha256(("admin" + salt).encode('utf-8')).hexdigest()
        cursor.execute("INSERT INTO users (id, username, password_hash, salt) VALUES (1, 'admin', ?, ?)", (password_hash, salt))
        
    # Insert default profile row for user 1 if not exists
    cursor.execute("SELECT COUNT(*) FROM profile WHERE user_id = 1")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
        INSERT INTO profile (user_id, name, email, phone, linkedin_url, github_url, portfolio_url, resume_filename, resume_text, gemini_api_key, linkedin_api_key, windows_daemon_enabled, monday_time, dry_run)
        VALUES (1, '', '', '', '', '', '', '', '', '', '', 0, '09:00', 1)
        """)

    conn.commit()
    conn.close()

# Profile Helpers
def get_profile(user_id=1):
    conn = get_db_connection()
    profile = conn.execute("SELECT * FROM profile WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    if profile:
        return dict(profile)
    return None

def update_profile(user_id, name, email, phone, linkedin_url, github_url, portfolio_url, resume_filename=None, resume_text=None, gemini_api_key=None, linkedin_api_key=None, windows_daemon_enabled=None, monday_time=None, dry_run=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Ensure profile row exists for this user_id
    cursor.execute("SELECT COUNT(*) FROM profile WHERE user_id = ?", (user_id,))
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO profile (user_id) VALUES (?)", (user_id,))
        conn.commit()
    
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
        "linkedin_api_key": linkedin_api_key,
        "windows_daemon_enabled": windows_daemon_enabled,
        "monday_time": monday_time,
        "dry_run": dry_run
    }
    
    for k, v in fields.items():
        if v is not None:
            updates.append(f"{k} = ?")
            params.append(v)
            
    if updates:
        params.append(user_id)
        query = f"UPDATE profile SET {', '.join(updates)} WHERE user_id = ?"
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
def add_to_queue(user_id, job_id, cover_letter=""):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR REPLACE INTO apply_queue (user_id, job_id, cover_letter) VALUES (?, ?, ?)", (user_id, job_id, cover_letter))
        conn.commit()
        success = True
    except Exception as e:
        print(f"Error adding to queue: {e}")
        success = False
    conn.close()
    return success

def remove_from_queue(user_id, job_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM apply_queue WHERE user_id = ? AND job_id = ?", (user_id, job_id))
    conn.commit()
    conn.close()

def get_queue(user_id):
    conn = get_db_connection()
    query = """
    SELECT q.id as queue_id, q.job_id, q.cover_letter, q.added_at, j.*
    FROM apply_queue q
    JOIN jobs_cache j ON q.job_id = j.id
    WHERE q.user_id = ?
    ORDER BY q.added_at ASC
    """
    queue_items = conn.execute(query, (user_id,)).fetchall()
    conn.close()
    return [dict(item) for item in queue_items]

def update_queue_cover_letter(user_id, job_id, cover_letter):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE apply_queue SET cover_letter = ? WHERE user_id = ? AND job_id = ?", (cover_letter, user_id, job_id))
    conn.commit()
    conn.close()

# History Helpers
def add_to_history(user_id, job_id, title, company, url, cover_letter, status, error_message=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO apply_history (user_id, job_id, title, company, url, cover_letter, status, error_message)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, job_id, title, company, url, cover_letter, status, error_message))
    
    # Once added to history, remove from the active queue
    cursor.execute("DELETE FROM apply_queue WHERE user_id = ? AND job_id = ?", (user_id, job_id))
    
    conn.commit()
    conn.close()

def get_history(user_id):
    conn = get_db_connection()
    history = conn.execute("SELECT * FROM apply_history WHERE user_id = ? ORDER BY applied_at DESC", (user_id,)).fetchall()
    conn.close()
    return [dict(item) for item in history]

def clear_history(user_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM apply_history WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

# User Auth Helpers
def get_user_by_username(username):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return dict(user) if user else None

def get_user_by_id(user_id):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(user) if user else None

def create_user(username, password):
    import hashlib
    import os
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        salt = os.urandom(16).hex()
        password_hash = hashlib.sha256((password + salt).encode('utf-8')).hexdigest()
        cursor.execute("INSERT INTO users (username, password_hash, salt) VALUES (?, ?, ?)", (username, password_hash, salt))
        user_id = cursor.lastrowid
        
        # Auto-create empty profile for new user
        cursor.execute("""
        INSERT INTO profile (user_id, name, email, phone, linkedin_url, github_url, portfolio_url, resume_filename, resume_text, gemini_api_key, linkedin_api_key, windows_daemon_enabled, monday_time, dry_run)
        VALUES (?, '', '', '', '', '', '', '', '', '', '', 0, '09:00', 1)
        """, (user_id,))
        
        conn.commit()
        success = True
    except Exception as e:
        print(f"Error creating user: {e}")
        success = False
        user_id = None
    conn.close()
    return success, user_id

def authenticate_user(username, password):
    import hashlib
    user = get_user_by_username(username)
    if not user:
        return None
    salt = user['salt']
    password_hash = hashlib.sha256((password + salt).encode('utf-8')).hexdigest()
    if password_hash == user['password_hash']:
        return user
    return None

def update_job_details(job_id, url, description):
    """
    Updates the cached URL and description for a job after resolving LinkedIn details.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE jobs_cache
    SET url = ?, description = ?
    WHERE id = ?
    """, (url, description, job_id))
    conn.commit()
    conn.close()

# Initialize on import
init_db()

