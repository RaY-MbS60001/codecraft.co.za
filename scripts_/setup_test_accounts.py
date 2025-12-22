# scripts_/setup_test_accounts.py

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import User, Application, CalendarEvent, LearnearshipOpportunity

with app.app_context():
    print("\n" + "=" * 80)
    print("🔐 SETTING UP TEST ACCOUNTS WITH SAMPLE DATA")
    print("=" * 80)
    
    # Define test users with passwords
    test_accounts = {
        'hr@techcorp.co.za': {
            'password': 'admin123',
            'name': 'Sarah Johnson',
            'role': 'corporate',
            'company': 'Tech Corp Solutions'
        },
        'recruiter@techcorp.co.za': {
            'password': 'admin123',
            'name': 'Mike Chen',
            'role': 'corporate',
            'company': 'Tech Corp Solutions'
        },
        'hiring@innovate.co.za': {
            'password': 'admin123',
            'name': 'Emma Watson',
            'role': 'corporate',
            'company': 'Innovate Digital'
        },
        'recruitment@finance.co.za': {
            'password': 'admin123',
            'name': 'James Thompson',
            'role': 'corporate',
            'company': 'Finance Pro Ltd'
        },
        'john.ndlovu@email.com': {
            'password': 'user123',
            'name': 'John Ndlovu',
            'role': 'applicant'
        },
        'aisha.mohammed@email.com': {
            'password': 'user123',
            'name': 'Aisha Mohammed',
            'role': 'applicant'
        },
        'david.smith@email.com': {
            'password': 'user123',
            'name': 'David Smith',
            'role': 'applicant'
        }
    }
    
    print("\n✅ Setting passwords for test accounts...\n")
    
    for email, data in test_accounts.items():
        user = User.query.filter_by(email=email).first()
        if user:
            user.set_password(data['password'])
            db.session.commit()
            print(f"✅ {data['name']:<25} ({email})")
            print(f"   Password: {data['password']}")
            print(f"   Role: {data['role']}")
            if 'company' in data:
                print(f"   Company: {data['company']}")
            print()
        else:
            print(f"❌ {email} - NOT FOUND")
    
    # Show corporate users with their data
    print("\n" + "=" * 80)
    print("📊 CORPORATE USERS & THEIR DATA")
    print("=" * 80)
    
    corporate_users = User.query.filter_by(role='corporate').all()
    
    for corp_user in corporate_users:
        print(f"\n👤 {corp_user.full_name}")
        print(f"   Email: {corp_user.email}")
        print(f"   Password: admin123")
        print(f"   Company: {corp_user.company_name}")
        print(f"   " + "-" * 76)
        
        # Count opportunities posted by this user
        opps = LearnearshipOpportunity.query.filter_by(company_id=corp_user.id).count()
        print(f"   📋 Opportunities Posted: {opps}")
        
        # Count applications assigned to this user
        apps = Application.query.filter_by(corporate_user_id=corp_user.id).count()
        print(f"   📤 Applications Managed: {apps}")
        
        # Count calendar events for this user
        events = CalendarEvent.query.filter_by(corporate_user_id=corp_user.id).count()
        print(f"   📅 Interviews Scheduled: {events}")
        
        # Show opportunities
        if opps > 0:
            print(f"\n   Job Opportunities Posted:")
            opportunities = LearnearshipOpportunity.query.filter_by(company_id=corp_user.id).all()
            for opp in opportunities:
                print(f"     • {opp.title}")
        
        # Show applications
        if apps > 0:
            print(f"\n   Applications Received:")
            applications = Application.query.filter_by(corporate_user_id=corp_user.id).all()
            for app in applications:
                applicant = User.query.get(app.user_id)
                print(f"     • {applicant.full_name} - {app.learnership_name} ({app.email_status})")
        
        # Show interviews
        if events > 0:
            print(f"\n   Interviews Scheduled:")
            interviews = CalendarEvent.query.filter_by(corporate_user_id=corp_user.id).all()
            for interview in interviews:
                applicant = User.query.get(interview.applicant_user_id)
                print(f"     • {applicant.full_name} - {interview.title}")
    
    # Show applicant users with their data
    print("\n\n" + "=" * 80)
    print("👥 APPLICANT USERS & THEIR DATA")
    print("=" * 80)
    
    applicant_users = User.query.filter_by(role='user').all()
    
    for applicant in applicant_users:
        print(f"\n👤 {applicant.full_name}")
        print(f"   Email: {applicant.email}")
        print(f"   Password: user123")
        print(f"   " + "-" * 76)
        
        # Count applications
        apps = Application.query.filter_by(user_id=applicant.id).count()
        print(f"   📤 Applications Submitted: {apps}")
        
        # Show applications
        if apps > 0:
            print(f"\n   Your Applications:")
            applications = Application.query.filter_by(user_id=applicant.id).all()
            for app in applications:
                print(f"     • {app.learnership_name} - Status: {app.email_status}")
    
    print("\n\n" + "=" * 80)
    print("🚀 HOW TO LOGIN & TEST")
    print("=" * 80)
    print("""
1. 🏢 CORPORATE DASHBOARD (Admin/HR):
   - Go to: http://localhost:5000/admin-login
   - Email: hr@techcorp.co.za
   - Password: admin123
   - Can access:
     ✅ Dashboard with analytics
     ✅ Applications list
     ✅ Calendar/Interviews
     ✅ Post opportunities
     ✅ Inbox

2. 👤 JOB SEEKER ACCOUNT:
   - Go to: http://localhost:5000/login
   - Email: john.ndlovu@email.com
   - Password: user123
   - Can access:
     ✅ Browse opportunities
     ✅ Apply to jobs
     ✅ View applications
     ✅ Track status

3. 📋 OTHER CORPORATE ACCOUNTS TO TEST:
   - recruiter@techcorp.co.za / admin123
   - hiring@innovate.co.za / admin123
   - recruitment@finance.co.za / admin123
""")
    print("=" * 80)