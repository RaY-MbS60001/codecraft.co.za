# scripts_/fix_missing_gmail_ids.py
"""
Script to find and add missing Gmail IDs to existing applications.
Run this once to fix applications that were sent before tracking was added.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
import json


def find_gmail_id_for_application(service, application, user_email):
    """Search Gmail for the sent email and return its ID"""
    try:
        # Build search queries to find the email
        queries = []
        
        # Try searching by company name in subject
        if application.company_name:
            queries.append(f'in:sent subject:"{application.company_name}"')
            queries.append(f'in:sent to:{application.company_name.lower().replace(" ", "")}')
        
        # Try by learnership name
        if application.learnership_name:
            queries.append(f'in:sent subject:"{application.learnership_name}"')
        
        # Generic application search
        queries.append('in:sent subject:"Application" OR subject:"Learnership"')
        
        for query in queries:
            print(f"    🔍 Trying query: {query[:50]}...")
            
            try:
                results = service.users().messages().list(
                    userId='me',
                    q=query,
                    maxResults=20
                ).execute()
                
                messages = results.get('messages', [])
                
                if not messages:
                    continue
                
                print(f"    📧 Found {len(messages)} potential matches")
                
                # Check each message
                for msg_info in messages:
                    try:
                        msg = service.users().messages().get(
                            userId='me',
                            id=msg_info['id'],
                            format='metadata',
                            metadataHeaders=['To', 'Subject', 'Date']
                        ).execute()
                        
                        # Get message date
                        internal_date = int(msg.get('internalDate', 0))
                        msg_date = datetime.fromtimestamp(internal_date / 1000)
                        
                        # Get headers
                        headers = {}
                        for header in msg.get('payload', {}).get('headers', []):
                            headers[header['name'].lower()] = header['value']
                        
                        subject = headers.get('subject', '')
                        to_email = headers.get('to', '')
                        
                        # Check if this matches our application
                        match_score = 0
                        
                        # Check company name in subject or to
                        if application.company_name:
                            company_lower = application.company_name.lower()
                            if company_lower in subject.lower():
                                match_score += 3
                            if company_lower in to_email.lower():
                                match_score += 3
                        
                        # Check date proximity
                        if application.sent_at:
                            time_diff = abs((msg_date - application.sent_at).total_seconds())
                            if time_diff < 3600:  # Within 1 hour
                                match_score += 5
                            elif time_diff < 86400:  # Within 1 day
                                match_score += 3
                            elif time_diff < 604800:  # Within 1 week
                                match_score += 1
                        elif application.submitted_at:
                            time_diff = abs((msg_date - application.submitted_at).total_seconds())
                            if time_diff < 86400:  # Within 1 day
                                match_score += 2
                        
                        # Check for application keywords
                        if 'application' in subject.lower() or 'learnership' in subject.lower():
                            match_score += 1
                        
                        if match_score >= 3:
                            print(f"    ✅ Match found! Score: {match_score}")
                            print(f"       Subject: {subject[:50]}")
                            print(f"       To: {to_email[:50]}")
                            print(f"       Date: {msg_date}")
                            print(f"       Message ID: {msg_info['id']}")
                            return msg_info['id'], msg.get('threadId')
                            
                    except Exception as e:
                        print(f"    ⚠️ Error checking message: {e}")
                        continue
                        
            except Exception as e:
                print(f"    ⚠️ Query failed: {e}")
                continue
        
        return None, None
        
    except Exception as e:
        print(f"    ❌ Error searching: {e}")
        return None, None


def fix_missing_gmail_ids():
    """Main function to fix missing Gmail IDs"""
    from app import app, db
    from models import Application, GoogleToken, User
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    
    with app.app_context():
        print("\n" + "=" * 70)
        print("🔧 FIXING MISSING GMAIL IDs FOR APPLICATION TRACKING")
        print("=" * 70)
        
        # Find applications without gmail_message_id
        apps = Application.query.filter(
            Application.gmail_message_id.is_(None)
        ).filter(
            Application.email_status.in_(['sent', 'pending', 'submitted', 'draft'])
        ).all()
        
        # Also check for apps with any status but no gmail ID
        all_apps_no_id = Application.query.filter(
            Application.gmail_message_id.is_(None)
        ).all()
        
        print(f"\n📊 STATISTICS:")
        print(f"   Applications without Gmail ID (sent/pending): {len(apps)}")
        print(f"   Total applications without Gmail ID: {len(all_apps_no_id)}")
        
        if not apps and not all_apps_no_id:
            print("\n✅ All applications already have Gmail IDs!")
            return
        
        # Use all apps without ID
        apps_to_fix = all_apps_no_id
        print(f"\n📋 Processing {len(apps_to_fix)} applications...")
        
        # Group by user
        user_apps = {}
        for application in apps_to_fix:
            if application.user_id not in user_apps:
                user_apps[application.user_id] = []
            user_apps[application.user_id].append(application)
        
        fixed_count = 0
        failed_count = 0
        
        for user_id, applications in user_apps.items():
            print(f"\n{'─' * 50}")
            print(f"👤 USER {user_id} ({len(applications)} applications)")
            print(f"{'─' * 50}")
            
            # Get user info
            user = User.query.get(user_id)
            if not user:
                print(f"   ❌ User not found!")
                failed_count += len(applications)
                continue
            
            print(f"   Email: {user.email}")
            
            # Get user's token
            token = GoogleToken.query.filter_by(user_id=user_id).first()
            if not token:
                print(f"   ❌ No Google token found - user needs to re-authenticate")
                failed_count += len(applications)
                continue
            
            try:
                # Build credentials
                token_data = json.loads(token.token_json)
                
                creds = Credentials(
                    token=token_data.get('access_token') or token_data.get('token'),
                    refresh_token=token_data.get('refresh_token'),
                    token_uri=token_data.get('token_uri', 'https://oauth2.googleapis.com/token'),
                    client_id=token_data.get('client_id') or app.config.get('GOOGLE_CLIENT_ID'),
                    client_secret=token_data.get('client_secret') or app.config.get('GOOGLE_CLIENT_SECRET')
                )
                
                # Refresh if needed
                if creds.expired and creds.refresh_token:
                    from google.auth.transport.requests import Request
                    creds.refresh(Request())
                    print(f"   🔄 Token refreshed")
                
                service = build('gmail', 'v1', credentials=creds)
                print(f"   ✅ Gmail service connected")
                
                # Process each application
                for application in applications:
                    print(f"\n   📄 Application #{application.id}")
                    print(f"      Company: {application.company_name or 'N/A'}")
                    print(f"      Learnership: {application.learnership_name or 'N/A'}")
                    print(f"      Status: {application.email_status}")
                    print(f"      Sent: {application.sent_at or application.submitted_at}")
                    
                    gmail_id, thread_id = find_gmail_id_for_application(
                        service, 
                        application,
                        user.email
                    )
                    
                    if gmail_id:
                        application.gmail_message_id = gmail_id
                        application.gmail_thread_id = thread_id
                        
                        # Update email_status if it was draft
                        if application.email_status in ['draft', 'pending']:
                            application.email_status = 'sent'
                        
                        db.session.commit()
                        fixed_count += 1
                        print(f"      ✅ FIXED! Gmail ID: {gmail_id[:20]}...")
                    else:
                        failed_count += 1
                        print(f"      ⚠️ Could not find matching email in Gmail")
                        print(f"         This email may have been sent via SMTP or deleted")
                        
                import time
                time.sleep(0.3)  # Rate limiting
                        
            except Exception as e:
                print(f"   ❌ Error: {e}")
                import traceback
                traceback.print_exc()
                failed_count += len(applications)
        
        # Summary
        print("\n" + "=" * 70)
        print("📊 SUMMARY")
        print("=" * 70)
        print(f"   ✅ Fixed: {fixed_count}")
        print(f"   ⚠️ Could not fix: {failed_count}")
        print(f"   📋 Total processed: {len(apps_to_fix)}")
        print("=" * 70)
        
        if fixed_count > 0:
            print("\n🎉 Gmail tracking should now work for the fixed applications!")
            print("   Run your status checker again to see the updates.")
        
        if failed_count > 0:
            print("\n💡 For applications that couldn't be fixed:")
            print("   - The emails may have been sent via SMTP (not Gmail API)")
            print("   - The emails may have been deleted from Gmail")
            print("   - New applications will automatically have tracking")


def show_application_details():
    """Show details of all applications"""
    from app import app, db
    from models import Application, User
    
    with app.app_context():
        apps = Application.query.all()
        
        print("\n" + "=" * 80)
        print("📋 ALL APPLICATIONS")
        print("=" * 80)
        print(f"{'ID':<5} {'User':<8} {'Company':<20} {'Status':<12} {'Gmail ID':<15} {'Sent'}")
        print("-" * 80)
        
        for app in apps:
            gmail_status = "✅" if app.gmail_message_id else "❌"
            gmail_id = app.gmail_message_id[:12] + "..." if app.gmail_message_id else "None"
            company = (app.company_name or "N/A")[:18]
            sent = app.sent_at.strftime("%Y-%m-%d") if app.sent_at else "N/A"
            
            print(f"{app.id:<5} {app.user_id:<8} {company:<20} {app.email_status:<12} {gmail_status} {gmail_id:<12} {sent}")
        
        print("-" * 80)
        
        # Stats
        with_id = sum(1 for a in apps if a.gmail_message_id)
        without_id = sum(1 for a in apps if not a.gmail_message_id)
        
        print(f"\n📊 Stats: {with_id} with Gmail ID, {without_id} without")


if __name__ == '__main__':
    import sys
    
    print("\n🔧 Gmail ID Fix Tool")
    print("=" * 40)
    print("1. Fix missing Gmail IDs")
    print("2. Show all applications")
    print("3. Exit")
    
    choice = input("\nChoose option (1-3): ").strip()
    
    if choice == '1':
        fix_missing_gmail_ids()
    elif choice == '2':
        show_application_details()
    else:
        print("Exiting...")