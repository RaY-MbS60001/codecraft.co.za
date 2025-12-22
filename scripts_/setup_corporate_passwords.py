# scripts_/setup_corporate_passwords.py

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import User, Application, CalendarEvent, LearnearshipOpportunity

with app.app_context():
    print("\n" + "=" * 90)
    print("🔐 SETTING UP CORPORATE TEST ACCOUNTS")
    print("=" * 90)
    
    # Corporate accounts
    corporate_accounts = [
        ('hr@techcorp.co.za', 'admin123'),
        ('recruiter@techcorp.co.za', 'admin123'),
        ('hiring@innovate.co.za', 'admin123'),
        ('recruitment@finance.co.za', 'admin123'),
    ]
    
    print("\n✅ Setting passwords for corporate users...\n")
    
    for email, password in corporate_accounts:
        user = User.query.filter_by(email=email).first()
        if user:
            user.set_password(password)
            db.session.commit()
            
            # Get stats
            opps = LearnearshipOpportunity.query.filter_by(company_id=user.id).count()
            apps = Application.query.filter_by(corporate_user_id=user.id).count()
            events = CalendarEvent.query.filter_by(corporate_user_id=user.id).count()
            
            print(f"✅ {user.full_name:<25} ({email})")
            print(f"   Password: {password}")
            print(f"   Company: {user.company_name}")
            print(f"   📋 Opportunities: {opps} | 📤 Applications: {apps} | 📅 Interviews: {events}")
            print()
    
    # Applicant accounts
    print("\n✅ Setting passwords for applicant users...\n")
    
    applicant_accounts = [
        ('john.ndlovu@email.com', 'user123'),
        ('aisha.mohammed@email.com', 'user123'),
        ('david.smith@email.com', 'user123'),
        ('thandeka.xaba@email.com', 'user123'),
        ('lisa.chen@email.com', 'user123'),
    ]
    
    for email, password in applicant_accounts:
        user = User.query.filter_by(email=email).first()
        if user:
            user.set_password(password)
            db.session.commit()
            
            apps = Application.query.filter_by(user_id=user.id).count()
            
            print(f"✅ {user.full_name:<25} ({email})")
            print(f"   Password: {password}")
            print(f"   📤 Applications: {apps}")
            print()
    
    print("\n" + "=" * 90)
    print("🚀 QUICK TEST GUIDE")
    print("=" * 90)
    print("""
┌─────────────────────────────────────────────────────────────────┐
│ 1️⃣  CORPORATE/HR LOGIN (Admin Dashboard)                        │
├─────────────────────────────────────────────────────────────────┤
│ URL: http://localhost:5000/admin-login                          │
│                                                                 │
│ 🏢 Tech Corp Solutions (HR):                                    │
│    Email: hr@techcorp.co.za                                     │
│    Pass:  admin123                                              │
│    Data: 2 opportunities, 8 applications, 4 interviews          │
│                                                                 │
│ 🏢 Tech Corp Solutions (Recruiter):                             │
│    Email: recruiter@techcorp.co.za                              │
│    Pass:  admin123                                              │
│                                                                 │
│ 🏢 Innovate Digital:                                            │
│    Email: hiring@innovate.co.za                                 │
│    Pass:  admin123                                              │
│                                                                 │
│ 🏢 Finance Pro Ltd:                                             │
│    Email: recruitment@finance.co.za                             │
│    Pass:  admin123                                              │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ 2️⃣  JOB SEEKER LOGIN                                            │
├─────────────────────────────────────────────────────────────────┤
│ URL: http://localhost:5000/login                                │
│                                                                 │
│ 👤 John Ndlovu:                                                 │
│    Email: john.ndlovu@email.com                                 │
│    Pass:  user123                                               │
│                                                                 │
│ 👤 Aisha Mohammed:                                              │
│    Email: aisha.mohammed@email.com                              │
│    Pass:  user123                                               │
│                                                                 │
│ 👤 David Smith:                                                 │
│    Email: david.smith@email.com                                 │
│    Pass:  user123                                               │
│                                                                 │
│ 👤 Thandeka Xaba:                                               │
│    Email: thandeka.xaba@email.com                               │
│    Pass:  user123                                               │
│                                                                 │
│ 👤 Lisa Chen:                                                   │
│    Email: lisa.chen@email.com                                   │
│    Pass:  user123                                               │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ 3️⃣  WHAT YOU CAN TEST IN CORPORATE DASHBOARD                    │
├─────────────────────────────────────────────────────────────────┤
│ ✅ Dashboard - View applications & analytics                    │
│ ✅ Applications - See all applications with status              │
│ ✅ Calendar - View scheduled interviews                         │
│ ✅ Opportunities - Create/edit job opportunities                │
│ ✅ Inbox - Conversations with applicants                        │
│ ✅ Analytics - See recruitment metrics                          │
└─────────────────────────────────────────────────────────────────┘

""")
    print("=" * 90)