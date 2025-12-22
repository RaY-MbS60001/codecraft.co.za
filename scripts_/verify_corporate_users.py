# scripts_/verify_corporate_users.py

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import User

with app.app_context():
    print("\n" + "=" * 80)
    print("✅ VERIFYING CORPORATE USERS")
    print("=" * 80 + "\n")
    
    # Corporate users to verify
    corporate_emails = [
        'hr@techcorp.co.za',
        'recruiter@techcorp.co.za',
        'hiring@innovate.co.za',
        'recruitment@finance.co.za',
    ]
    
    for email in corporate_emails:
        user = User.query.filter_by(email=email).first()
        
        if user:
            user.is_verified = True
            db.session.commit()
            
            print(f"✅ {user.full_name}")
            print(f"   Email: {email}")
            print(f"   Status: VERIFIED ✓")
            print(f"   Company: {user.company_name}")
            print()
        else:
            print(f"❌ {email} NOT FOUND\n")
    
    print("=" * 80)
    print("\n🚀 NOW YOU CAN LOGIN!\n")
    print("   URL: http://localhost:5000/admin-login")
    print("   Username: hr_techcorp") 
    print("   Password: admin123")
    print()