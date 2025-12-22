# scripts_/create_sample_corporate_data.py

import sqlite3
import os
from datetime import datetime, timedelta
import random

# ============================================================
# CONFIGURATION
# ============================================================
DB_PATH = "instance/codecraft.db"

# ============================================================
# DATABASE CONNECTION
# ============================================================

def connect_db():
    """Connect to local SQLite database"""
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found: {DB_PATH}")
        return None
    
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return None

# ============================================================
# SAMPLE DATA GENERATORS
# ============================================================

def create_sample_corporate_users(conn):
    """Create sample corporate/admin users"""
    cursor = conn.cursor()
    
    print("\n👥 Creating sample corporate users...")
    
    corporate_users = [
        {
            'email': 'hr@techcorp.co.za',
            'full_name': 'Sarah Johnson',
            'username': 'sarah_johnson',
            'password_hash': 'pbkdf2:sha256:600000$hash1',
            'role': 'corporate',
            'auth_method': 'email',
            'phone': '0721234567',
            'company_name': 'Tech Corp Solutions',
            'company_email': 'hr@techcorp.co.za',
            'company_website': 'https://techcorp.co.za',
            'is_active': 1,
        },
        {
            'email': 'recruiter@techcorp.co.za',
            'full_name': 'Mike Chen',
            'username': 'mike_chen',
            'password_hash': 'pbkdf2:sha256:600000$hash2',
            'role': 'corporate',
            'auth_method': 'email',
            'phone': '0723456789',
            'company_name': 'Tech Corp Solutions',
            'company_email': 'hr@techcorp.co.za',
            'company_website': 'https://techcorp.co.za',
            'is_active': 1,
        },
        {
            'email': 'hiring@innovate.co.za',
            'full_name': 'Emma Watson',
            'username': 'emma_watson',
            'password_hash': 'pbkdf2:sha256:600000$hash3',
            'role': 'corporate',
            'auth_method': 'email',
            'phone': '0725678901',
            'company_name': 'Innovate Digital',
            'company_email': 'hiring@innovate.co.za',
            'company_website': 'https://innovate.co.za',
            'is_active': 1,
        },
        {
            'email': 'recruitment@finance.co.za',
            'full_name': 'James Thompson',
            'username': 'james_thompson',
            'password_hash': 'pbkdf2:sha256:600000$hash4',
            'role': 'corporate',
            'auth_method': 'email',
            'phone': '0726789012',
            'company_name': 'Finance Pro Ltd',
            'company_email': 'recruitment@finance.co.za',
            'company_website': 'https://financepro.co.za',
            'is_active': 1,
        },
    ]
    
    inserted = 0
    for user in corporate_users:
        try:
            cursor.execute("""
                INSERT INTO user (email, username, password_hash, full_name, role, auth_method,
                                phone, company_name, company_email, company_website, 
                                is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user['email'], user['username'], user['password_hash'], user['full_name'],
                user['role'], user['auth_method'], user['phone'], user['company_name'],
                user['company_email'], user['company_website'], user['is_active'], datetime.utcnow()
            ))
            inserted += 1
            print(f"  ✅ Created: {user['full_name']} ({user['email']})")
        except sqlite3.IntegrityError:
            print(f"  ℹ️  Already exists: {user['email']}")
        except Exception as e:
            print(f"  ❌ Error: {e}")
    
    conn.commit()
    print(f"✅ Inserted {inserted} corporate users")
    
    return inserted

def create_sample_applicants(conn):
    """Create sample job applicants"""
    cursor = conn.cursor()
    
    print("\n👤 Creating sample applicants...")
    
    applicants = [
        {
            'email': 'john.ndlovu@email.com',
            'full_name': 'John Ndlovu',
            'username': 'john_ndlovu',
            'password_hash': 'pbkdf2:sha256:600000$hash5',
            'role': 'user',
            'auth_method': 'email',
            'phone': '0787654321',
            'address': 'Johannesburg, Gauteng',
        },
        {
            'email': 'aisha.mohammed@email.com',
            'full_name': 'Aisha Mohammed',
            'username': 'aisha_mohammed',
            'password_hash': 'pbkdf2:sha256:600000$hash6',
            'role': 'user',
            'auth_method': 'email',
            'phone': '0789876543',
            'address': 'Cape Town, Western Cape',
        },
        {
            'email': 'david.smith@email.com',
            'full_name': 'David Smith',
            'username': 'david_smith',
            'password_hash': 'pbkdf2:sha256:600000$hash7',
            'role': 'user',
            'auth_method': 'email',
            'phone': '0781234567',
            'address': 'Durban, KwaZulu-Natal',
        },
        {
            'email': 'thandeka.xaba@email.com',
            'full_name': 'Thandeka Xaba',
            'username': 'thandeka_xaba',
            'password_hash': 'pbkdf2:sha256:600000$hash8',
            'role': 'user',
            'auth_method': 'email',
            'phone': '0782345678',
            'address': 'Pretoria, Gauteng',
        },
        {
            'email': 'lisa.chen@email.com',
            'full_name': 'Lisa Chen',
            'username': 'lisa_chen',
            'password_hash': 'pbkdf2:sha256:600000$hash9',
            'role': 'user',
            'auth_method': 'email',
            'phone': '0783456789',
            'address': 'Johannesburg, Gauteng',
        },
    ]
    
    inserted = 0
    for applicant in applicants:
        try:
            cursor.execute("""
                INSERT INTO user (email, username, password_hash, full_name, role, auth_method,
                                phone, address, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                applicant['email'], applicant['username'], applicant['password_hash'],
                applicant['full_name'], applicant['role'], applicant['auth_method'],
                applicant['phone'], applicant['address'], 1, datetime.utcnow()
            ))
            inserted += 1
            print(f"  ✅ Created: {applicant['full_name']} ({applicant['email']})")
        except sqlite3.IntegrityError:
            print(f"  ℹ️  Already exists: {applicant['email']}")
        except Exception as e:
            print(f"  ❌ Error: {e}")
    
    conn.commit()
    print(f"✅ Inserted {inserted} applicants")
    
    return inserted

def create_sample_opportunities(conn):
    """Create sample learnership opportunities"""
    cursor = conn.cursor()
    
    print("\n📋 Creating sample learnership opportunities...")
    
    # Get corporate user IDs
    cursor.execute("SELECT id FROM user WHERE role = 'corporate' LIMIT 2")
    corporate_ids = [row[0] for row in cursor.fetchall()]
    
    if not corporate_ids:
        print("❌ No corporate users found!")
        return 0
    
    opportunities = [
        {
            'company_id': corporate_ids[0],
            'title': 'Senior Python Developer Learnership',
            'description': 'Join our tech team as a Senior Python Developer. Work with modern tech stack and mentor junior developers.',
            'requirements': '5+ years Python experience, Django/FastAPI knowledge',
            'benefits': 'Competitive stipend, mentorship, career growth',
            'location': 'Johannesburg',
            'duration': '12 months',
            'stipend': 'R8,000 - R12,000/month',
            'application_email': 'hr@techcorp.co.za',
            'max_applicants': 10,
        },
        {
            'company_id': corporate_ids[0],
            'title': 'Data Analyst Learnership',
            'description': 'Analyze complex datasets and provide insights. Great opportunity to develop data skills.',
            'requirements': 'SQL, Excel, Basic Python',
            'benefits': 'Hands-on experience, mentorship, networking',
            'location': 'Johannesburg',
            'duration': '6 months',
            'stipend': 'R5,000 - R7,000/month',
            'application_email': 'hr@techcorp.co.za',
            'max_applicants': 5,
        },
        {
            'company_id': corporate_ids[1] if len(corporate_ids) > 1 else corporate_ids[0],
            'title': 'Digital Marketing Manager Learnership',
            'description': 'Lead digital marketing campaigns and social media strategy for our growing company.',
            'requirements': 'Social media experience, content creation, basic SEO',
            'benefits': 'Portfolio building, industry connections, stipend',
            'location': 'Cape Town',
            'duration': '12 months',
            'stipend': 'R6,000 - R9,000/month',
            'application_email': 'hiring@innovate.co.za',
            'max_applicants': 8,
        },
        {
            'company_id': corporate_ids[1] if len(corporate_ids) > 1 else corporate_ids[0],
            'title': 'Financial Analyst Learnership',
            'description': 'Analyze financial data, prepare reports, and support financial planning.',
            'requirements': 'Excel, Basic accounting knowledge',
            'benefits': 'CFA mentorship, real-world experience, career path',
            'location': 'Pretoria',
            'duration': '12 months',
            'stipend': 'R7,000 - R10,000/month',
            'application_email': 'recruitment@finance.co.za',
            'max_applicants': 6,
        },
    ]
    
    inserted = 0
    for opp in opportunities:
        try:
            deadline = datetime.utcnow() + timedelta(days=30)
            cursor.execute("""
                INSERT INTO learnership_opportunity 
                (company_id, title, description, requirements, benefits, location, 
                 duration, stipend, application_email, application_deadline, max_applicants, 
                 is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                opp['company_id'], opp['title'], opp['description'], opp['requirements'],
                opp['benefits'], opp['location'], opp['duration'], opp['stipend'],
                opp['application_email'], deadline, opp['max_applicants'], 1, datetime.utcnow()
            ))
            inserted += 1
            print(f"  ✅ Created: {opp['title']}")
        except Exception as e:
            print(f"  ⚠️  Error: {e}")
    
    conn.commit()
    print(f"✅ Inserted {inserted} opportunities")
    
    return inserted

def create_sample_applications(conn):
    """Create sample applications - NO created_at field"""
    cursor = conn.cursor()
    
    print("\n📤 Creating sample applications...")
    
    # Get user IDs
    cursor.execute("SELECT id FROM user WHERE role = 'user'")
    applicant_ids = [row[0] for row in cursor.fetchall()]
    
    cursor.execute("SELECT id FROM learnership_opportunity")
    opp_ids = [row[0] for row in cursor.fetchall()]
    
    cursor.execute("SELECT id FROM user WHERE role = 'corporate'")
    corporate_ids = [row[0] for row in cursor.fetchall()]
    
    if not applicant_ids or not opp_ids or not corporate_ids:
        print("❌ Missing required data!")
        return 0
    
    email_statuses = ['draft', 'sent', 'delivered', 'read']
    app_statuses = ['pending', 'reviewed', 'shortlisted', 'rejected']
    
    inserted = 0
    app_id = 1
    
    for applicant_id in applicant_ids:
        for opp_id in random.sample(opp_ids, min(2, len(opp_ids))):
            try:
                submitted_at = datetime.utcnow() - timedelta(days=random.randint(1, 20))
                email_status = random.choice(email_statuses)
                app_status = random.choice(app_statuses)
                
                # Get opportunity details
                cursor.execute("SELECT title FROM learnership_opportunity WHERE id = ?", (opp_id,))
                opp_result = cursor.fetchone()
                opp_title = opp_result[0] if opp_result else f"Opportunity {opp_id}"
                
                has_gmail = email_status != 'draft'
                gmail_msg_id = f"gmail_{app_id}@gmail.com" if has_gmail else None
                sent_at = submitted_at if has_gmail else None
                
                cursor.execute("""
                    INSERT INTO application 
                    (user_id, company_name, learnership_name, status, 
                     submitted_at, email_status, gmail_message_id, 
                     sent_at, updated_at, corporate_user_id, application_stage)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    applicant_id, f"Company {random.choice([1,2,3,4])}", opp_title,
                    app_status, submitted_at, email_status, gmail_msg_id, sent_at, 
                    submitted_at, random.choice(corporate_ids), 'applied'
                ))
                inserted += 1
                app_id += 1
                print(f"  ✅ Created application #{inserted}")
            except Exception as e:
                print(f"  ⚠️  Error: {e}")
    
    conn.commit()
    print(f"✅ Inserted {inserted} applications")
    
    return inserted

def create_sample_calendar_events(conn):
    """Create sample calendar events (interviews)"""
    cursor = conn.cursor()
    
    print("\n📅 Creating sample calendar events...")
    
    # Get application IDs
    cursor.execute("SELECT id, user_id FROM application LIMIT 8")
    apps = cursor.fetchall()
    
    # Get a corporate user
    cursor.execute("SELECT id FROM user WHERE role = 'corporate' LIMIT 1")
    corp_result = cursor.fetchone()
    if not corp_result:
        print("❌ No corporate users found!")
        return 0
    
    corporate_id = corp_result[0]
    
    if not apps:
        print("❌ No applications found!")
        return 0
    
    inserted = 0
    for app in apps:
        app_id, applicant_id = app
        
        interview_date = datetime.utcnow() + timedelta(days=random.randint(1, 30))
        hour = random.choice([9, 10, 11, 14, 15, 16])
        start_time = interview_date.replace(hour=hour, minute=0, second=0, microsecond=0)
        end_time = start_time + timedelta(hours=1)
        
        try:
            cursor.execute("""
                INSERT INTO calendar_event 
                (application_id, corporate_user_id, applicant_user_id, event_type,
                 title, description, start_datetime, end_datetime, location, 
                 status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                app_id, corporate_id, applicant_id, 'interview',
                'Technical Interview Round 1', 
                'Initial technical assessment and company overview',
                start_time, end_time, 'Virtual - Google Meet',
                'scheduled', datetime.utcnow()
            ))
            inserted += 1
            print(f"  ✅ Scheduled interview for Application #{app_id}")
        except Exception as e:
            print(f"  ⚠️  Error: {e}")
    
    conn.commit()
    print(f"✅ Inserted {inserted} calendar events")
    
    return inserted

def create_sample_documents(conn):
    """Create sample documents"""
    cursor = conn.cursor()
    
    print("\n📄 Creating sample documents...")
    
    cursor.execute("SELECT id FROM user WHERE role = 'user'")
    applicant_ids = [row[0] for row in cursor.fetchall()]
    
    if not applicant_ids:
        print("❌ No applicants found!")
        return 0
    
    documents = [
        ('CV_John_Ndlovu.pdf', 'CV', applicant_ids[0] if len(applicant_ids) > 0 else None),
        ('Cover_Letter.docx', 'cover_letter', applicant_ids[0] if len(applicant_ids) > 0 else None),
        ('CV_Aisha_Mohammed.pdf', 'CV', applicant_ids[1] if len(applicant_ids) > 1 else None),
        ('Portfolio.zip', 'portfolio', applicant_ids[2] if len(applicant_ids) > 2 else None),
        ('CV_David_Smith.pdf', 'CV', applicant_ids[2] if len(applicant_ids) > 2 else None),
        ('CV_Thandeka_Xaba.pdf', 'CV', applicant_ids[3] if len(applicant_ids) > 3 else None),
    ]
    
    inserted = 0
    for filename, doc_type, user_id in documents:
        if not user_id:
            continue
        try:
            cursor.execute("""
                INSERT INTO document 
                (user_id, document_type, filename, original_filename, file_size, uploaded_at, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id, doc_type, filename, filename, random.randint(100000, 5000000), 
                datetime.utcnow(), 1
            ))
            inserted += 1
            print(f"  ✅ Created: {filename}")
        except Exception as e:
            print(f"  ⚠️  Error: {e}")
    
    conn.commit()
    print(f"✅ Inserted {inserted} documents")
    
    return inserted

def create_sample_conversations(conn):
    """Create sample conversations"""
    cursor = conn.cursor()
    
    print("\n💬 Creating sample conversations...")
    
    # Get applications with sent emails
    cursor.execute("""
        SELECT id, user_id FROM application 
        WHERE email_status IN ('sent', 'delivered', 'read') 
        LIMIT 6
    """)
    apps = cursor.fetchall()
    
    # Get corporate user
    cursor.execute("SELECT id FROM user WHERE role = 'corporate' LIMIT 1")
    corp_result = cursor.fetchone()
    if not corp_result:
        print("⚠️  No corporate users found!")
        return 0
    
    corporate_id = corp_result[0]
    
    if not apps:
        print("⚠️  No eligible applications!")
        return 0
    
    inserted = 0
    conv_id = 1
    
    for app in apps:
        app_id, applicant_id = app
        
        try:
            cursor.execute("""
                INSERT INTO conversation 
                (application_id, gmail_thread_id, subject, 
                 corporate_user_id, applicant_user_id, is_active, 
                 last_message_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                app_id, f"thread_{conv_id}@gmail.com",
                "Re: Your Learnership Application",
                corporate_id, applicant_id, 1,
                datetime.utcnow(), datetime.utcnow()
            ))
            inserted += 1
            conv_id += 1
            print(f"  ✅ Created conversation for Application #{app_id}")
        except Exception as e:
            print(f"  ⚠️  Error: {e}")
    
    conn.commit()
    print(f"✅ Inserted {inserted} conversations")
    
    return inserted

def create_sample_google_tokens(conn):
    """Create sample Google tokens"""
    cursor = conn.cursor()
    
    print("\n🔐 Creating sample Google tokens...")
    
    cursor.execute("SELECT id, email FROM user WHERE role = 'corporate'")
    corporate_users = cursor.fetchall()
    
    if not corporate_users:
        print("❌ No corporate users found!")
        return 0
    
    inserted = 0
    for user_id, email in corporate_users[:2]:
        try:
            token_json = f'{{"access_token": "sample_access_{user_id}", "refresh_token": "sample_refresh_{user_id}"}}'
            
            cursor.execute("""
                INSERT INTO google_token 
                (user_id, token_json, refreshed_at)
                VALUES (?, ?, ?)
            """, (
                user_id, token_json, datetime.utcnow()
            ))
            inserted += 1
            print(f"  ✅ Created token for: {email}")
        except sqlite3.IntegrityError:
            print(f"  ℹ️  Token already exists for: {email}")
    
    conn.commit()
    print(f"✅ Inserted {inserted} Google tokens")
    
    return inserted

def show_database_summary(conn):
    """Show summary of created data"""
    cursor = conn.cursor()
    
    print("\n" + "=" * 70)
    print("📊 DATABASE SUMMARY")
    print("=" * 70)
    
    tables = [
        ('user', 'Total Users'),
        ('learnership_opportunity', 'Total Opportunities'),
        ('application', 'Total Applications'),
        ('calendar_event', 'Total Interviews'),
        ('conversation', 'Total Conversations'),
        ('document', 'Total Documents'),
        ('google_token', 'Total Google Tokens'),
    ]
    
    for table, label in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  {label:<25}: {count:>5}")
        except:
            print(f"  {label:<25}: Error")
    
    print("=" * 70)

# ============================================================
# MAIN EXECUTION
# ============================================================

def main():
    print("=" * 70)
    print("📊 CREATE SAMPLE CORPORATE DATA FOR TESTING")
    print("=" * 70)
    
    conn = connect_db()
    if not conn:
        return
    
    try:
        total_created = 0
        
        total_created += create_sample_corporate_users(conn)
        total_created += create_sample_applicants(conn)
        total_created += create_sample_opportunities(conn)
        total_created += create_sample_applications(conn)
        total_created += create_sample_calendar_events(conn)
        total_created += create_sample_documents(conn)
        total_created += create_sample_conversations(conn)
        total_created += create_sample_google_tokens(conn)
        
        show_database_summary(conn)
        
        print("\n✅ SAMPLE DATA CREATION COMPLETE!")
        print(f"   Total items created: {total_created}")
        
        print("\n🔑 CORPORATE TEST ACCOUNTS:")
        print("   ┌─────────────────────────────────────────┐")
        print("   │ Email: hr@techcorp.co.za                │")
        print("   │ Name:  Sarah Johnson                    │")
        print("   ├─────────────────────────────────────────┤")
        print("   │ Email: recruiter@techcorp.co.za         │")
        print("   │ Name:  Mike Chen                        │")
        print("   ├─────────────────────────────────────────┤")
        print("   │ Email: hiring@innovate.co.za            │")
        print("   │ Name:  Emma Watson                      │")
        print("   ├─────────────────────────────────────────┤")
        print("   │ Email: recruitment@finance.co.za        │")
        print("   │ Name:  James Thompson                   │")
        print("   └─────────────────────────────────────────┘")
        
        print("\n👤 APPLICANT TEST ACCOUNTS:")
        print("   ┌─────────────────────────────────────────┐")
        print("   │ john.ndlovu@email.com                   │")
        print("   │ aisha.mohammed@email.com                │")
        print("   │ david.smith@email.com                   │")
        print("   │ thandeka.xaba@email.com                 │")
        print("   │ lisa.chen@email.com                     │")
        print("   └─────────────────────────────────────────┘")
        
        print("\n🧪 WHAT YOU CAN TEST:")
        print("   ✅ Corporate dashboard with applications")
        print("   ✅ Calendar with scheduled interviews")
        print("   ✅ Conversations/email threads")
        print("   ✅ Application status tracking")
        print("   ✅ Analytics and metrics")
        print("   ✅ Document management")
        
        print("\n=" * 70)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        conn.close()
        print("\n👋 Done!")

if __name__ == "__main__":
    main()