# learnership_emails.py
from datetime import datetime

learnership_email_data = [
    {"id": 1, "company_name": "TEST MAIL", "email": "sfisomabaso12242001@gmail.com", "status": "checking", "last_checked": None, "response_time": None},
    {"id": 2, "company_name": "Diversity Empowerment", "email": "Info@diversityempowerment.co.za", "status": "checking", "last_checked": None, "response_time": None},
    {"id": 3, "company_name": "Sparrow Portal", "email": "Enquiries@sparrowportal.co.za", "status": "checking", "last_checked": None, "response_time": None},
    {"id": 4, "company_name": "Impactful", "email": "Sihle.Nyanga@impactful.co.za", "status": "checking", "last_checked": None, "response_time": None},
    {"id": 5, "company_name": "CSG Skills", "email": "mseleke@csgskills.co.za", "status": "checking", "last_checked": None, "response_time": None}
]

def get_all_emails():
    return [item["email"] for item in learnership_email_data]

def get_email_by_company(company_name):
    for item in learnership_email_data: 
        if item["company_name"].lower() == company_name.lower(): return item["email"]
    return None

def update_email_status(email, status, response_time=None):
    for item in learnership_email_data:
        if item["email"] == email: item.update({"status": status, "last_checked": datetime.utcnow(), "response_time": response_time})

def get_reachable_emails():
    return [item for item in learnership_email_data if item["status"] == "reachable"]

def get_email_status(email):
    for item in learnership_email_data:
        if item["email"] == email: return item
    return None