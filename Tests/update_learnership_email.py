from app import app
from models import db, LearnshipEmail
from sqlalchemy import func  # Import func directly from sqlalchemy
with app.app_context():
    new_email = "sfisomabaso12242001@gmail.com"
    new_company = "mbs"
    
    # Find the record with this email
    existing = LearnshipEmail.query.filter_by(email=new_email).first()
    
    if existing:
        # Update the existing record's company name
        old_company = existing.company_name
        existing.company_name = new_company
        db.session.commit()
        print(f"Updated existing record - Company changed from {old_company} to {new_company}")
    else:
        # Email doesn't exist, so update a random record
        email_to_update = LearnshipEmail.query.order_by(func.random()).first()
        if email_to_update:
            old_email = email_to_update.email
            email_to_update.email = new_email
            email_to_update.company_name = new_company
            db.session.commit()
            print(f"Updated email from {old_email} to {new_email}")