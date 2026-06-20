import re
import os
import requests
import json
import google.generativeai as genai
import database

def clean_html(text):
    """
    Remove HTML tags for plain text cover letters or parsing.
    """
    if not text:
        return ""
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)

def generate_cover_letter(profile, job_title, company, job_description):
    """
    Generates a cover letter. If a Gemini API Key is available, uses the Gemini API.
    Otherwise, falls back to a clean, professional template.
    """
    api_key = profile.get('gemini_api_key', '')
    resume_text = profile.get('resume_text', '')
    name = profile.get('name', 'Applicant')
    email = profile.get('email', '')
    phone = profile.get('phone', '')
    linkedin = profile.get('linkedin_url', '')
    github = profile.get('github_url', '')
    
    clean_desc = clean_html(job_description)

    if api_key:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            prompt = f"""
            You are an expert career advisor and professional writer. Create a compelling, professional cover letter tailored for the job below.
            
            Applicant Information:
            - Name: {name}
            - Email: {email}
            - Phone: {phone}
            - LinkedIn: {linkedin}
            - GitHub: {github}
            - Resume Content:
            \"\"\"{resume_text}\"\"\"
            
            Job Information:
            - Title: {job_title}
            - Company: {company}
            - Description:
            \"\"\"{clean_desc}\"\"\"
            
            Instructions:
            - Keep the cover letter concise (around 250-300 words).
            - Focus on matching the applicant's relevant experience and skills with the job requirements.
            - Write in a professional, confident tone.
            - Start with a clear introduction, 1-2 body paragraphs emphasizing fit, and a professional closing.
            - Return ONLY the cover letter text. Do not include subject lines, markdown code block wrappers (like ```), or commentary.
            """
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            print(f"Gemini generation error, falling back to template: {e}")
            # Fall back to template

    # Professional template fallback
    skills_list = ", ".join(profile.get('skills', ['Software Development', 'Problem Solving', 'Engineering'])[:5]) if isinstance(profile.get('skills'), list) else "Software Engineering"
    
    cover_letter = f"""Dear Hiring Team,

I am writing to express my strong interest in the {job_title} position at {company}. With a solid foundation in software development and experience with key tools like {skills_list}, I am confident in my ability to contribute value to your team.

My background matches many of the key requirements of this role. I have worked on projects demonstrating my ability to build clean, maintainable code and solve complex technical challenges. I am a quick learner who thrives in collaborative environments, and I am eager to apply my skills to the engineering initiatives at {company}.

Thank you for your time and consideration of my application. I have attached my resume for your review and look forward to the opportunity to discuss how my qualifications align with the needs of your team.

Sincerely,
{name}
{email} | {phone}
{linkedin}
"""
    return cover_letter

def apply_lever(company, posting_id, profile, cover_letter):
    """
    Submits application to Lever's public posting API:
    POST https://api.lever.co/v0/postings/{company}/{posting_id}/apply
    """
    if profile.get('dry_run', 1) == 1:
        return True, "Dry Run: Simulated application submission via Lever API."

    url = f"https://api.lever.co/v0/postings/{company}/{posting_id}/apply"
    
    # Check resume file
    resume_filename = profile.get('resume_filename', '')
    data_dir = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
    resume_path = os.path.join(data_dir, resume_filename) if resume_filename else None
    
    if not resume_path or not os.path.exists(resume_path):
        return False, "Resume file not found. Please upload a resume first."

    files = {
        'resume': (os.path.basename(resume_path), open(resume_path, 'rb'), 'application/pdf')
    }
    
    data = {
        'name': profile.get('name', ''),
        'email': profile.get('email', ''),
        'phone': profile.get('phone', ''),
        'urls[LinkedIn]': profile.get('linkedin_url', ''),
        'urls[GitHub]': profile.get('github_url', ''),
        'urls[Portfolio]': profile.get('portfolio_url', ''),
        'comments': cover_letter
    }
    
    try:
        # User-Agent is needed sometimes to bypass basic blocking
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.post(url, data=data, files=files, headers=headers, timeout=30)
        
        # Lever returns 200 or 204 on success, or redirect.
        if response.status_code in [200, 201, 204]:
            return True, "Successfully submitted application via Lever API."
        else:
            return False, f"Lever API Error (Status {response.status_code}): {response.text[:200]}"
    except Exception as e:
        return False, f"Request failed: {str(e)}"
    finally:
        if 'resume' in files:
            files['resume'][1].close()

def apply_greenhouse(company, job_id, profile, cover_letter):
    """
    Submits application to Greenhouse's candidate board endpoint:
    POST https://boards.greenhouse.io/embed/job_board/js?for={company} (or the application endpoint)
    Greenhouse applications typically go to:
    POST https://boards.greenhouse.io/{company}/jobs/{job_id}/apply
    OR standard boards-api:
    POST https://boards-api.greenhouse.io/v1/boards/{company}/jobs/{job_id}/apply (though boards-api is read-only sometimes without auth, the form submission is public)
    """
    if profile.get('dry_run', 1) == 1:
        return True, "Dry Run: Simulated application submission via Greenhouse Form API."

    # For robust form submission, we can post to the public board apply URL
    url = f"https://boards.greenhouse.io/{company}/jobs/{job_id}/apply"
    
    resume_filename = profile.get('resume_filename', '')
    data_dir = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
    resume_path = os.path.join(data_dir, resume_filename) if resume_filename else None
    
    if not resume_path or not os.path.exists(resume_path):
        return False, "Resume file not found. Please upload a resume first."

    files = {
        'resume': (os.path.basename(resume_path), open(resume_path, 'rb'), 'application/pdf')
    }
    
    # Greenhouse standard fields
    # NOTE: Greenhouse forms use custom field IDs for some questions, but name, email, phone, resume, cover_letter, and linkedin are standard
    data = {
        'first_name': profile.get('name', '').split(' ')[0] if ' ' in profile.get('name', '') else profile.get('name', ''),
        'last_name': ' '.join(profile.get('name', '').split(' ')[1:]) if ' ' in profile.get('name', '') else 'Applicant',
        'email': profile.get('email', ''),
        'phone': profile.get('phone', ''),
        'cover_letter_text': cover_letter,
        'urls[linkedin]': profile.get('linkedin_url', ''),
        'urls[github]': profile.get('github_url', ''),
        'urls[website]': profile.get('portfolio_url', '')
    }
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # In Greenhouse, submitting the form directly might redirect or return 200/302.
        response = requests.post(url, data=data, files=files, headers=headers, allow_redirects=False, timeout=30)
        
        # If redirected (302) to confirmation page or returns 200, consider it a success.
        if response.status_code in [200, 201, 302]:
            return True, "Successfully submitted application via Greenhouse Form API."
        else:
            return False, f"Greenhouse Form Error (Status {response.status_code}): {response.text[:200]}"
    except Exception as e:
        return False, f"Request failed: {str(e)}"
    finally:
        if 'resume' in files:
            files['resume'][1].close()

def apply_to_job(profile, job, cover_letter):
    """
    Orchestrates application submission. Detects ATS (Lever/Greenhouse) and executes.
    If not supported, returns requires_manual.
    """
    job_url = job.get('url', '')
    
    # 1. Check Lever
    # Lever URL patterns: https://jobs.lever.co/company_name/posting_id
    lever_match = re.search(r'jobs\.lever\.co/([^/]+)/([^/?\s]+)', job_url)
    if lever_match:
        company = lever_match.group(1)
        posting_id = lever_match.group(2)
        print(f"Applying to Lever job. Company: {company}, Posting ID: {posting_id}")
        return apply_lever(company, posting_id, profile, cover_letter)
        
    # 2. Check Greenhouse
    # Greenhouse URL patterns: https://boards.greenhouse.io/company_name/jobs/job_id
    gh_match = re.search(r'boards\.greenhouse\.io/([^/]+)/jobs/(\d+)', job_url)
    if gh_match:
        company = gh_match.group(1)
        job_id = gh_match.group(2)
        print(f"Applying to Greenhouse job. Company: {company}, Job ID: {job_id}")
        return apply_greenhouse(company, job_id, profile, cover_letter)
        
    # 3. Fallback: Requires manual submission
    return False, "requires_manual"

def run_auto_apply_queue():
    """
    Processes all items currently in the apply_queue database.
    Updates application history and logs.
    """
    profile = database.get_profile()
    if not profile or not profile.get('email'):
        print("Profile is incomplete. Cannot run application queue.")
        return 0
        
    queue = database.get_queue()
    if not queue:
        print("Queue is empty. Nothing to apply to.")
        return 0
        
    applied_count = 0
    print(f"Starting auto-apply process for {len(queue)} jobs...")
    
    for item in queue:
        job_id = item['job_id']
        title = item['title']
        company = item['company']
        url = item['url']
        cover_letter = item['cover_letter']
        
        # If cover letter is empty, generate it now
        if not cover_letter:
            cover_letter = generate_cover_letter(profile, title, company, item['description'])
            
        success, message = apply_to_job(profile, item, cover_letter)
        
        if success:
            database.add_to_history(job_id, title, company, url, cover_letter, 'completed', message)
            applied_count += 1
            print(f"Successfully applied to {title} at {company}")
        elif message == "requires_manual":
            database.add_to_history(job_id, title, company, url, cover_letter, 'requires_manual', "Non-standard job site. Cover letter pre-generated. Submit manually.")
            print(f"Job requires manual submission: {title} at {company}")
        else:
            database.add_to_history(job_id, title, company, url, cover_letter, 'failed', message)
            print(f"Failed to apply to {title} at {company}: {message}")
            
    return applied_count
