# scripts_/populate_all_corporate_data.py

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import User, Application, CalendarEvent, LearnearshipOpportunity
from datetime import datetime, timedelta
import random

with app.app_context():
    print("\n" + "=" * 90)
    print("📊 POPULATING ALL CORPORATE USERS WITH SAMPLE DATA")
    print("=" * 90 + "\n")
    
    # Get all corporate users
    corporate_users = User.query.filter_by(role='corporate').all()
    
    if not corporate_users:
        print("❌ No corporate users found!")
        exit()
    
    # Get all applicant users
    applicants = User.query.filter_by(role='user').all()
    
    if not applicants:
        print("❌ No applicant users found!")
        exit()
    
    print(f"✅ Found {len(corporate_users)} corporate users")
    print(f"✅ Found {len(applicants)} applicant users\n")
    
    # For each corporate user, create opportunities and applications
    for corp_user in corporate_users:
        print(f"\n👤 Setting up data for: {corp_user.full_name}")
        print(f"   Company: {corp_user.company_name}")
        print("-" * 90)
        
        # Create 3 opportunities for each corporate user
        opp_titles = [
            f'Senior Developer at {corp_user.company_name}',
            f'Data Analyst at {corp_user.company_name}',
            f'UX Designer at {corp_user.company_name}',
        ]
        
        created_opps = []
        for title in opp_titles:
            try:
                opp = LearnearshipOpportunity(
                    company_id=corp_user.id,
                    title=title,
                    description=f'Exciting opportunity to work with {corp_user.company_name}',
                    requirements='Relevant experience required',
                    benefits='Competitive stipend, mentorship, career growth',
                    location='Johannesburg',
                    duration='12 months',
                    stipend='R6,000 - R12,000/month',
                    application_email=corp_user.company_email or corp_user.email,
                    application_deadline=datetime.utcnow() + timedelta(days=30),
                    max_applicants=10,
                    is_active=True
                )
                db.session.add(opp)
                db.session.flush()
                created_opps.append(opp)
                print(f"   ✅ Created opportunity: {title}")
            except Exception as e:
                print(f"   ❌ Error creating opportunity: {e}")
        
        db.session.commit()
        
        # Create applications from applicants to these opportunities
        app_count = 0
        for applicant in applicants:
            # Each applicant applies to 2-3 opportunities
            for opp in random.sample(created_opps, min(2, len(created_opps))):
                try:
                    submitted_at = datetime.utcnow() - timedelta(days=random.randint(1, 20))
                    email_status = random.choice(['sent', 'delivered', 'read'])
                    app_status = random.choice(['pending', 'reviewed', 'shortlisted'])
                    
                    app = Application(
                        user_id=applicant.id,
                        company_name=corp_user.company_name,
                        learnership_name=opp.title,
                        status=app_status,
                        submitted_at=submitted_at,
                        email_status=email_status,
                        corporate_user_id=corp_user.id,
                        application_stage='reviewed',
                        sent_at=submitted_at,
                        gmail_message_id=f"gmail_{corp_user.id}_{applicant.id}_{opp.id}@gmail.com"
                    )
                    db.session.add(app)
                    db.session.flush()
                    app_count += 1
                    
                except Exception as e:
                    print(f"   ❌ Error creating application: {e}")
        
        db.session.commit()
        print(f"   ✅ Created {app_count} applications")
        
        # Create calendar events for some applications
        event_count = 0
        apps_for_events = Application.query.filter_by(corporate_user_id=corp_user.id).limit(3).all()
        
        for app in apps_for_events:
            try:
                interview_date = datetime.utcnow() + timedelta(days=random.randint(1, 30))
                start_time = interview_date.replace(hour=random.choice([9, 10, 14, 15]), minute=0, second=0, microsecond=0)
                end_time = start_time + timedelta(hours=1)
                
                event = CalendarEvent(
                    application_id=app.id,
                    corporate_user_id=corp_user.id,
                    applicant_user_id=app.user_id,
                    event_type='interview',
                    title='Technical Interview',
                    description='Initial technical assessment and company overview',
                    start_datetime=start_time,
                    end_datetime=end_time,
                    location='Virtual - Google Meet',
                    status='scheduled'
                )
                db.session.add(event)
                db.session.flush()
                event_count += 1
                
            except Exception as e:
                print(f"   ❌ Error creating event: {e}")
        
        db.session.commit()
        print(f"   ✅ Created {event_count} interview events")
    
    print("\n" + "=" * 90)
    print("✅ DATA POPULATION COMPLETE!")
    print("=" * 90 + "\n")
    
    # Show summary
    print("📊 FINAL DATA SUMMARY:\n")
    for corp_user in corporate_users:
        opps = LearnearshipOpportunity.query.filter_by(company_id=corp_user.id).count()
        apps = Application.query.filter_by(corporate_user_id=corp_user.id).count()
        events = CalendarEvent.query.filter_by(corporate_user_id=corp_user.id).count()
        
        print(f"👤 {corp_user.full_name}")
        print(f"   Username: {corp_user.username}")
        print(f"   📋 Opportunities: {opps}")
        print(f"   📤 Applications: {apps}")
        print(f"   📅 Interviews: {events}")
        print()
    
    print("=" * 90)
    print("\n🚀 READY TO TEST! Login with any of these:\n")
    
    for corp_user in corporate_users:
        print(f"   {corp_user.username} / admin123")
    
    print()