import urllib.request
import json
import re
from datetime import datetime
import database

def clean_html(raw_html):
    """
    Optional helper to clean up HTML tags if needed, 
    but we can also keep it for rendering in the dashboard.
    """
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext

def is_internship_check(title, description):
    """
    Checks if a job title or description indicates it's an internship.
    """
    pattern = r'\b(intern|internship|co-op|trainee|undergrad)\b'
    text_to_check = f"{title} {description}".lower()
    return 1 if re.search(pattern, text_to_check) else 0

def fetch_jobicy_jobs(count=50):
    url = f"https://jobicy.com/api/v2/remote-jobs?count={count}"
    jobs_normalized = []
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            if data.get('success'):
                for job in data.get('jobs', []):
                    job_id = f"jobicy_{job.get('id')}"
                    title = job.get('jobTitle', '')
                    company = job.get('companyName', '')
                    company_logo = job.get('companyLogo', '')
                    job_url = job.get('url', '')
                    location = job.get('jobGeo', 'Remote')
                    description = job.get('jobDescription', '')
                    pub_date = job.get('pubDate', '')
                    is_intern = is_internship_check(title, description)
                    
                    jobs_normalized.append({
                        "id": job_id,
                        "title": title,
                        "company": company,
                        "company_logo": company_logo,
                        "url": job_url,
                        "location": location,
                        "source": "Jobicy",
                        "description": description,
                        "pub_date": pub_date,
                        "is_internship": is_intern
                    })
    except Exception as e:
        print(f"Error fetching from Jobicy: {e}")
    return jobs_normalized

def fetch_remotive_jobs(limit=50):
    url = f"https://remotive.com/api/remote-jobs?limit={limit}"
    jobs_normalized = []
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            for job in data.get('jobs', []):
                job_id = f"remotive_{job.get('id')}"
                title = job.get('title', '')
                company = job.get('company_name', '')
                company_logo = job.get('company_logo', '')
                job_url = job.get('url', '')
                location = job.get('candidate_required_location', 'Remote')
                description = job.get('description', '')
                pub_date = job.get('publication_date', '')
                is_intern = is_internship_check(title, description)
                
                # Standardize Remotive pub_date (e.g., '2024-05-18T10:00:00')
                if 'T' in pub_date:
                    pub_date = pub_date.replace('T', ' ')
                    if '.' in pub_date:
                        pub_date = pub_date.split('.')[0]
                
                jobs_normalized.append({
                    "id": job_id,
                    "title": title,
                    "company": company,
                    "company_logo": company_logo,
                    "url": job_url,
                    "location": location,
                    "source": "Remotive",
                    "description": description,
                    "pub_date": pub_date,
                    "is_internship": is_intern
                })
    except Exception as e:
        print(f"Error fetching from Remotive: {e}")
    return jobs_normalized

def fetch_greenhouse_jobs(companies=["figma", "vercel", "reddit", "cloudflare"]):
    jobs_normalized = []
    for company in companies:
        url = f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode('utf-8'))
                for job in data.get('jobs', []):
                    job_id = f"greenhouse_{job.get('id')}"
                    title = job.get('title', '')
                    comp_name = company.capitalize()
                    if company == "vercel":
                        comp_name = "Vercel"
                    elif company == "cloudflare":
                        comp_name = "Cloudflare"
                        
                    job_url = job.get('absolute_url', f"https://boards.greenhouse.io/{company}/jobs/{job.get('id')}")
                    location_dict = job.get('location')
                    location = location_dict.get('name', 'Remote') if isinstance(location_dict, dict) else 'Remote'
                    description = job.get('content', '')
                    pub_date = job.get('updated_at', '')
                    
                    # Convert to standard format
                    if pub_date and 'T' in pub_date:
                        pub_date = pub_date.replace('T', ' ')
                        if '.' in pub_date:
                            pub_date = pub_date.split('.')[0]
                        elif '-' in pub_date[10:]: # strip timezone offset if present
                            pub_date = pub_date.split('-')[0] + '-' + pub_date.split('-')[1] + '-' + pub_date.split('-')[2][:2]
                            
                    is_intern = is_internship_check(title, description)
                    
                    jobs_normalized.append({
                        "id": job_id,
                        "title": title,
                        "company": comp_name,
                        "company_logo": "",
                        "url": job_url,
                        "location": location,
                        "source": f"Greenhouse ({comp_name})",
                        "description": description,
                        "pub_date": pub_date,
                        "is_internship": is_intern
                    })
        except Exception as e:
            print(f"Error fetching Greenhouse jobs for {company}: {e}")
    return jobs_normalized

def fetch_lever_jobs(companies=["zoox"]):
    jobs_normalized = []
    for company in companies:
        url = f"https://api.lever.co/v0/postings/{company}?mode=json"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode('utf-8'))
                for job in data:
                    job_id = f"lever_{job.get('id')}"
                    title = job.get('text', '')
                    comp_name = company.capitalize()
                    if company == "zoox":
                        comp_name = "Zoox"
                        
                    job_url = job.get('hostedUrl', '')
                    categories = job.get('categories', {})
                    location = categories.get('location', 'Remote')
                    description = (job.get('descriptionHtml', '') or '') + "\n" + (job.get('additional', '') or '')
                    
                    created_at_ts = job.get('createdAt', 0)
                    pub_date = datetime.fromtimestamp(created_at_ts / 1000.0).strftime('%Y-%m-%d %H:%M:%S') if created_at_ts else ''
                    
                    is_intern = is_internship_check(title, description)
                    
                    jobs_normalized.append({
                        "id": job_id,
                        "title": title,
                        "company": comp_name,
                        "company_logo": "",
                        "url": job_url,
                        "location": location,
                        "source": f"Lever ({comp_name})",
                        "description": description,
                        "pub_date": pub_date,
                        "is_internship": is_intern
                    })
        except Exception as e:
            print(f"Error fetching Lever jobs for {company}: {e}")
    return jobs_normalized

def sync_jobs():
    """
    Fetches latest jobs from all sources, standardizes them, and saves to database cache.
    Returns the count of new/updated jobs.
    """
    print("Syncing jobs from all sources...")
    jobicy_jobs = fetch_jobicy_jobs(count=50)
    remotive_jobs = fetch_remotive_jobs(limit=50)
    greenhouse_jobs = fetch_greenhouse_jobs()
    lever_jobs = fetch_lever_jobs()
    
    all_jobs = jobicy_jobs + remotive_jobs + greenhouse_jobs + lever_jobs
    if all_jobs:
        database.save_jobs(all_jobs)
        return len(all_jobs)
    return 0

