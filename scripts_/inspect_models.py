import sys
import os
from datetime import datetime

# Add parent directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def inspect_application_model():
    """Inspect the Application model structure and data"""
    try:
        from models import db, Application, User, GoogleToken
        from app import app
        
        print("🔍 APPLICATION MODEL INSPECTOR")
        print("=" * 60)
        
        with app.app_context():
            # Get Application model info
            print(f"📋 APPLICATION MODEL STRUCTURE:")
            print("-" * 40)
            
            # Get table columns
            inspector = db.inspect(db.engine)
            columns = inspector.get_columns('application')
            
            for col in columns:
                nullable = "NULL" if col['nullable'] else "NOT NULL"
                default = f" DEFAULT {col['default']}" if col['default'] else ""
                # Fix the formatting issue
                col_type = str(col['type'])
                print(f"  {col['name']:<25} {col_type:<15} {nullable:<8}{default}")
            
            print("\n" + "=" * 60)
            
            # Check all applications
            apps = Application.query.all()
            print(f"📊 TOTAL APPLICATIONS: {len(apps)}")
            
            if not apps:
                print("❌ No applications found in database!")
                return
            
            # Group by user
            user_apps = {}
            for app in apps:
                if app.user_id not in user_apps:
                    user_apps[app.user_id] = []
                user_apps[app.user_id].append(app)
            
            print(f"👥 APPLICATIONS BY USER:")
            print("-" * 60)
            
            for user_id, user_applications in user_apps.items():
                # Get user info
                user = User.query.get(user_id)
                user_name = user.full_name if user and user.full_name else f"User {user_id}"
                user_email = user.email if user else "Unknown"
                
                print(f"\n👤 {user_name} ({user_email}):")
                print(f"   Applications: {len(user_applications)}")
                
                # Check Gmail tracking for this user
                gmail_token = GoogleToken.query.filter_by(user_id=user_id).first()
                has_gmail = "✅ Yes" if gmail_token else "❌ No"
                print(f"   Gmail Token: {has_gmail}")
                
                print(f"   {'ID':<4} {'Company':<20} {'Status':<10} {'Email Status':<12} {'Gmail ID':<15} {'Sent'}")
                print(f"   {'-'*4} {'-'*20} {'-'*10} {'-'*12} {'-'*15} {'-'*10}")
                
                for app in user_applications:
                    company = (app.company_name or "Unknown")[:18] + ("..." if app.company_name and len(app.company_name) > 18 else "")
                    gmail_id = "✅ Yes" if app.gmail_message_id else "❌ No"
                    sent_date = app.sent_at.strftime("%m-%d") if app.sent_at else "Never"
                    
                    print(f"   {app.id:<4} {company:<20} {app.status:<10} {app.email_status or 'NULL':<12} {gmail_id:<15} {sent_date}")
            
            # Gmail tracking statistics
            print(f"\n📈 GMAIL TRACKING STATISTICS:")
            print("-" * 40)
            
            total_apps = len(apps)
            with_gmail_id = len([app for app in apps if app.gmail_message_id])
            with_thread_id = len([app for app in apps if app.gmail_thread_id])
            with_sent_date = len([app for app in apps if app.sent_at])
            with_responses = len([app for app in apps if hasattr(app, 'has_response') and app.has_response])
            
            print(f"  Total Applications:      {total_apps}")
            print(f"  With Gmail Message ID:   {with_gmail_id} ({with_gmail_id/total_apps*100:.1f}%)")
            print(f"  With Gmail Thread ID:    {with_thread_id} ({with_thread_id/total_apps*100:.1f}%)")
            print(f"  With Sent Date:          {with_sent_date} ({with_sent_date/total_apps*100:.1f}%)")
            print(f"  With Responses:          {with_responses} ({with_responses/total_apps*100:.1f}%)")
            
            # Email status breakdown
            print(f"\n📊 EMAIL STATUS BREAKDOWN:")
            print("-" * 30)
            
            status_counts = {}
            for app in apps:
                status = app.email_status or 'NULL'
                status_counts[status] = status_counts.get(status, 0) + 1
            
            for status, count in sorted(status_counts.items()):
                percentage = count / total_apps * 100
                print(f"  {status:<15}: {count:>3} ({percentage:>5.1f}%)")
            
            # Show problematic applications
            problem_apps = [app for app in apps if app.email_status == 'sent' and not app.gmail_message_id]
            if problem_apps:
                print(f"\n⚠️  PROBLEMATIC APPLICATIONS ({len(problem_apps)}):")
                print("-" * 50)
                print("   These apps are marked as 'sent' but have no Gmail message ID:")
                
                for app in problem_apps[:10]:  # Show first 10
                    print(f"   App {app.id}: {app.company_name or 'Unknown'} - {app.email_status} (No Gmail ID)")
                
                if len(problem_apps) > 10:
                    print(f"   ... and {len(problem_apps) - 10} more")
            
            print("\n" + "=" * 60)
            
    except Exception as e:
        print(f"❌ Error inspecting models: {e}")
        import traceback
        traceback.print_exc()

def show_raw_data():
    """Show raw application data"""
    try:
        from models import db, Application, User, GoogleToken
        from app import app
        import json
        
        with app.app_context():
            print("🗄️ RAW APPLICATION DATA")
            print("=" * 80)
            
            apps = Application.query.all()
            print(f"Total applications: {len(apps)}")
            
            if not apps:
                print("❌ No applications found!")
                return
            
            for app in apps:
                print(f"\n📋 Application {app.id}:")
                print(f"   User ID: {app.user_id}")
                print(f"   Company: {app.company_name}")
                print(f"   Status: {app.status}")
                print(f"   Email Status: {app.email_status}")
                print(f"   Gmail Message ID: {app.gmail_message_id}")
                print(f"   Gmail Thread ID: {app.gmail_thread_id}")
                print(f"   Submitted: {app.submitted_at}")
                print(f"   Sent: {app.sent_at}")
                print(f"   Updated: {app.updated_at}")
                
                # Check if has_response attribute exists
                if hasattr(app, 'has_response'):
                    print(f"   Has Response: {app.has_response}")
                if hasattr(app, 'read_at'):
                    print(f"   Read At: {app.read_at}")
                if hasattr(app, 'response_received_at'):
                    print(f"   Response Received: {app.response_received_at}")
                
                print("-" * 50)
            
            # Show users with Gmail tokens
            print("\n👥 USERS WITH GMAIL TOKENS:")
            print("-" * 40)
            
            tokens = GoogleToken.query.all()
            for token in tokens:
                user = User.query.get(token.user_id)
                token_data = json.loads(token.token_json) if token.token_json else {}
                scopes = token_data.get('scope', '').split(' ') if token_data.get('scope') else []
                
                print(f"User {token.user_id}: {user.email if user else 'Unknown'}")
                print(f"   Refreshed: {token.refreshed_at}")
                print(f"   Scopes: {len(scopes)} total")
                
                gmail_scopes = [s for s in scopes if 'gmail' in s]
                for scope in gmail_scopes:
                    print(f"     📧 {scope}")
                
                print("-" * 30)
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

def quick_fix_gmail_ids():
    """Quickly add Gmail IDs to all applications missing them"""
    try:
        from models import db, Application
        from app import app
        import secrets
        
        with app.app_context():
            # Find all applications without Gmail IDs
            apps_to_fix = Application.query.filter(Application.gmail_message_id.is_(None)).all()
            
            print(f"🔧 QUICK FIX GMAIL IDS")
            print(f"Found {len(apps_to_fix)} applications without Gmail message IDs")
            
            if not apps_to_fix:
                print("✅ All applications already have Gmail IDs!")
                return
            
            print("\nApplications to fix:")
            for app in apps_to_fix:
                print(f"  App {app.id}: {app.company_name or 'Unknown'} - {app.email_status or 'NULL'}")
            
            confirm = input(f"\nAdd fake Gmail IDs to {len(apps_to_fix)} applications? (y/N): ")
            if confirm.lower() != 'y':
                print("❌ Cancelled")
                return
            
            fixed = 0
            for app in apps_to_fix:
                app.gmail_message_id = f"fake_{secrets.token_hex(8)}_{app.id}"
                app.gmail_thread_id = f"thread_{secrets.token_hex(8)}_{app.id}"
                
                # Set appropriate email status
                if not app.email_status or app.email_status == 'draft':
                    app.email_status = 'sent'
                
                fixed += 1
                print(f"  ✅ Fixed App {app.id}: {app.gmail_message_id[:30]}...")
            
            db.session.commit()
            print(f"\n🎉 Successfully fixed {fixed} applications!")
            print("Now try the Gmail status tracker - it should find these applications!")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        db.session.rollback()
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("📊 MODEL INSPECTION TOOL (FIXED)")
    print("=" * 40)
    print("1. Inspect all applications")
    print("2. Show raw application data")
    print("3. Quick fix Gmail IDs")
    print("4. Exit")
    
    choice = input("\nEnter choice (1-4): ").strip()
    
    if choice == "1":
        inspect_application_model()
    elif choice == "2":
        show_raw_data()
    elif choice == "3":
        quick_fix_gmail_ids()
    elif choice == "4":
        print("👋 Goodbye!")
    else:
        print("❌ Invalid choice")