# scripts_/fix_admin_login.py

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import User

with app.app_context():
    print("\n" + "=" * 80)
    print("🔐 FIXING ADMIN LOGIN - SETTING USERNAMES")
    print("=" * 80 + "\n")
    
    # Corporate users with their desired usernames
    users_data = [
        ('hr@techcorp.co.za', 'hr_techcorp', 'admin123'),
        ('recruiter@techcorp.co.za', 'recruiter_techcorp', 'admin123'),
        ('hiring@innovate.co.za', 'hiring_innovate', 'admin123'),
        ('recruitment@finance.co.za', 'recruitment_finance', 'admin123'),
    ]
    
    for email, username, password in users_data:
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Set username
            user.username = username
            # Set password
            user.set_password(password)
            db.session.commit()
            
            print(f"✅ {user.full_name}")
            print(f"   Email: {email}")
            print(f"   Username: {username}")
            print(f"   Password: {password}")
            print()
        else:
            print(f"❌ {email} NOT FOUND\n")
    
    print("=" * 80)
    print("\n🚀 NOW USE THIS TO LOGIN:\n")
    print("   URL: http://localhost:5000/admin-login")
    print("   Username: hr_techcorp")
    print("   Password: admin123")
    print()