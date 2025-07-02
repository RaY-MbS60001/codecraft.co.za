# init_db.py
from app import app, db
from models import User, LearnshipEmail

def init_database():
    with app.app_context():
        # Create all tables
        db.create_all()
        
        # Check if admin user exists
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            # Create default admin user
            admin = User(
                email='admin@codecraftco.com',
                username='admin',
                full_name='System Administrator',
                role='admin',
                auth_method='credentials',
                is_active=True
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("Admin user created successfully!")
            print("Username: admin")
            print("Password: admin123")
        else:
            print("Admin user already exists!")
        
        print("Database initialized successfully!")

def init_learnership_emails():
    """Initialize the database with learnership email addresses"""
    with app.app_context():
        # Check if emails already exist
        if LearnshipEmail.query.first() is not None:
            print("Learnership emails already exist in database. Skipping initialization.")
            return
        
        # List of email addresses with company names
        email_data = [
            {"company_name": "MBS", "email": "sfisomabaso12242001@gmail.com"},
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
    init_database()
    
    # Also initialize learnership emails
    init_learnership_emails()