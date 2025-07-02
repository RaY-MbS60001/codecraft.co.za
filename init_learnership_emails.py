# init_learnership_emails.py
from app import app, db
from models import LearnshipEmail

def init_learnership_emails():
    """Initialize the database with learnership email addresses"""
    with app.app_context():
        # Check if emails already exist
        if LearnshipEmail.query.first() is not None:
            print("Learnership emails already exist in database. Skipping initialization.")
            return
        
        # List of email addresses with company names
        email_data = [
            {"company_name": "Tych", "email": "Precious@tych.co.za"},
            {"company_name": "Progression", "email": "farhana@progression.co.za"},
            {"company_name": "QASA", "email": "recruitment@qasa.co.za"},
            {"company_name": "TLO", "email": "Recruitment@tlo.co.za"},
            {"company_name": "Dibanisa Learning", "email": "Slindile@dibanisaleaening.co.za"},
            {"company_name": "Tric Talent", "email": "Anatte@trictalent.co.za"},
            {"company_name": "Novia One", "email": "Tai@noviaone.com"},
            {"company_name": "Edge Executive", "email": "kgotso@edgexec.co.za"},
            {"company_name": "Related Ed", "email": "kagiso@related-ed.com"},
            {"company_name": "Skills Panda", "email": "refiloe@skillspanda.co.za"},
            {"company_name": "RMA Education", "email": "Skills@rma.edu.co.za"},
            {"company_name": "Signa", "email": "nkhensani@signa.co.za"},
            {"company_name": "CSG Skills", "email": "Sdube@csgskills.co.za"},
            {"company_name": "SITA", "email": "Lerato.recruitment@sita.co.za"},
            {"company_name": "TJH Business", "email": "melviln@tjhbusiness.co.za"},
            {"company_name": "Thandsh C", "email": "Moodleyt@thandshc.co.za"},
            {"company_name": "Kunaku", "email": "leaners@kunaku.co.za"},
            {"company_name": "KLM Empowered", "email": "leanership@klmempowerd.com"}
        ]
        
        # Add email addresses to the database
        for data in email_data:
            email = LearnshipEmail(company_name=data["company_name"], email=data["email"])
            db.session.add(email)
        
        db.session.commit()
        print(f"Added {len(email_data)} learnership emails to the database")

if __name__ == '__main__':
    init_learnership_emails()
    