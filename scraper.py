import urllib.request
import urllib.parse
import json
import re
from datetime import datetime
from bs4 import BeautifulSoup
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

def fetch_linkedin_guest_jobs(keywords="software intern", location="United States", limit=25):
    """
    Scrapes LinkedIn's public guest job postings without API keys.
    """
    kw_encoded = urllib.parse.quote(keywords)
    loc_encoded = urllib.parse.quote(location)
    
    url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={kw_encoded}&location={loc_encoded}&start=0"
    
    jobs_normalized = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            html = response.read().decode('utf-8')
            soup = BeautifulSoup(html, 'html.parser')
            
            job_cards = soup.find_all('li')
            for card in job_cards[:limit]:
                # Extract Job ID
                entity_urn = card.find('div', {'class': 'base-card'})
                if not entity_urn or not entity_urn.has_attr('data-entity-urn'):
                    continue
                urn_val = entity_urn['data-entity-urn']
                job_id = f"linkedin_{urn_val.split(':')[-1]}"
                
                # Extract Title
                title_elem = card.find('h3', {'class': 'base-search-card__title'})
                title = title_elem.text.strip() if title_elem else "Software Engineer"
                
                # Extract Company
                company_elem = card.find('a', {'class': 'hidden-nested-link'}) or card.find('h4', {'class': 'base-search-card__subtitle'})
                company = company_elem.text.strip() if company_elem else "Unknown Company"
                
                # Extract Location
                loc_elem = card.find('span', {'class': 'job-search-card__location'})
                job_location = loc_elem.text.strip() if loc_elem else location
                
                # Extract URL
                url_elem = card.find('a', {'class': 'base-card__full-link'})
                job_url = url_elem['href'].split('?')[0] if url_elem else ""
                
                # Description snippet
                description = f"LinkedIn Job Posting for {title} at {company} in {job_location}."
                
                is_intern = is_internship_check(title, description)
                
                jobs_normalized.append({
                    "id": job_id,
                    "title": title,
                    "company": company,
                    "company_logo": "",
                    "url": job_url,
                    "location": job_location,
                    "source": "LinkedIn (Guest)",
                    "description": description,
                    "pub_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "is_internship": is_intern
                })
    except Exception as e:
        print(f"Error scraping LinkedIn: {e}")
        
    return jobs_normalized

def resolve_linkedin_job(job_id):
    """
    Fetches the detailed LinkedIn guest job page to resolve the actual description
    and external application link (e.g., Lever/Greenhouse) if available.
    """
    numeric_id = job_id.split('_')[-1] if '_' in job_id else job_id
    url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{numeric_id}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            html = response.read().decode('utf-8')
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extract description
            desc_div = soup.find('div', {'class': 'description__text'}) or soup.find('section', {'class': 'description'})
            description = desc_div.text.strip() if desc_div else None
            
            # Extract apply link
            apply_url = None
            apply_button = soup.find('a', class_=re.compile(r'apply-button', re.I)) or soup.find('button', class_=re.compile(r'apply-button', re.I))
            if apply_button and apply_button.name == 'a' and apply_button.has_attr('href'):
                apply_url = apply_button['href']
                
            if not apply_url:
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    if "externalApply" in href:
                        apply_url = href
                        break
                        
            if not apply_url:
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    if "lever.co" in href or "greenhouse.io" in href:
                        apply_url = href
                        break
                        
            resolved_url = None
            if apply_url:
                parsed_url = urllib.parse.urlparse(apply_url)
                query_params = urllib.parse.parse_qs(parsed_url.query)
                if 'url' in query_params:
                    resolved_url = query_params['url'][0]
                else:
                    resolved_url = apply_url
                    
            return resolved_url, description
    except Exception as e:
        print(f"Error resolving LinkedIn job {job_id}: {e}")
        return None, None

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
    linkedin_jobs = fetch_linkedin_guest_jobs(keywords="software intern", location="United States")
    
    all_jobs = jobicy_jobs + remotive_jobs + greenhouse_jobs + lever_jobs + linkedin_jobs
    if all_jobs:
        database.save_jobs(all_jobs)
        return len(all_jobs)
    return 0

