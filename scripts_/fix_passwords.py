# scripts_/fix_passwords.py

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import User

with app.app_context():
    print("\n" + "=" * 80)
    print("🔐 FIXING CORPORATE USER PASSWORDS")
    print("=" * 80 + "\n")
    
    # List of corporate users to fix
    users_to_fix = [
        'hr@techcorp.co.za',
        'recruiter@techcorp.co.za',
        'hiring@innovate.co.za',
        'recruitment@finance.co.za',
    ]
    
    for email in users_to_fix:
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Set new password
            user.set_password('admin123')
            db.session.commit()
            
            print(f"✅ {user.full_name}")
            print(f"   Email: {email}")
            print(f"   Password: admin123")
            print(f"   Password Hash: {user.password_hash[:30]}...")
            print()
        else:
            print(f"❌ {email} NOT FOUND\n")
    
    print("=" * 80)
    print("\n🚀 Ready to login! Use:")
    print("   URL: http://localhost:5000/admin-login")
    print("   Email: hr@techcorp.co.za")
    print("   Password: admin123")
    print()