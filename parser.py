import re
from pypdf import PdfReader

def parse_resume_pdf(file_path):
    """
    Extracts text from a PDF file using pypdf.
    Returns the full text and some basic metadata (email, phone, name estimation).
    """
    try:
        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        
        # Extract basic info using regexes
        email = extract_email(text)
        phone = extract_phone(text)
        skills = extract_skills(text)
        
        return {
            "text": text.strip(),
            "email": email,
            "phone": phone,
            "skills": skills,
            "success": True
        }
    except Exception as e:
        return {
            "text": "",
            "email": "",
            "phone": "",
            "skills": [],
            "success": False,
            "error": str(e)
        }

def extract_email(text):
    email_re = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+')
    match = email_re.search(text)
    return match.group(0) if match else ""

def extract_phone(text):
    # Matches various formats: +1-123-456-7890, (123) 456-7890, 1234567890, etc.
    phone_re = re.compile(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}')
    match = phone_re.search(text)
    return match.group(0) if match else ""

def extract_skills(text):
    # A list of common skills to scan for in the text (simple keyword matching)
    common_skills = [
        "python", "javascript", "typescript", "react", "node.js", "node", "express", "html", "css", 
        "sql", "nosql", "mongodb", "postgresql", "mysql", "sqlite", "git", "docker", "aws", "gcp", 
        "azure", "machine learning", "deep learning", "nlp", "c++", "c#", "java", "go", "rust", 
        "flutter", "react native", "django", "flask", "fastapi", "spring", "docker", "kubernetes",
        "excel", "powerpoint", "word", "tableau", "power bi", "agile", "scrum", "jira"
    ]
    found_skills = []
    text_lower = text.lower()
    for skill in common_skills:
        # Match with word boundaries to avoid false positives (like 'go' matching 'good')
        pattern = rf"\b{re.escape(skill)}\b"
        if re.search(pattern, text_lower):
            # Format nicely
            found_skills.append(skill.title() if skill not in ["html", "css", "sql", "nosql", "aws", "gcp", "nlp", "api"] else skill.upper())
    return found_skills
