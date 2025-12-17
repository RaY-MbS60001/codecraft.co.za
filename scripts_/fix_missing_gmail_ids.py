# scripts_/fix_missing_gmail_ids_complete.py
"""
COMPLETE Enhanced script to find and add missing Gmail IDs to existing applications.
FIXED: Authentication scopes, query typos, and complete processing logic
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
import json
import time


def check_gmail_scopes(service, user_email):
    """Check if the user has required Gmail scopes"""
    try:
        # Try a simple test query first
        results = service.users().messages().list(
            userId='me',
            q='in:sent',
            maxResults=1
        ).execute()
        return True
    except Exception as e:
        if 'insufficientPermissions' in str(e) or 'insufficient authentication scopes' in str(e):
            return False
        raise e


def find_gmail_id_for_application(service, application, user_email):
    """Search Gmail for the sent email and return its ID with improved matching"""
    try:
        # First check if we have the right permissions
        if not check_gmail_scopes(service, user_email):
            print(f"    ❌ Insufficient Gmail permissions for {user_email}")
            print(f"       User needs to re-authenticate with Gmail API scopes")
            return None, None
        
        # Build targeted search queries (FIXED: removed typo "sentt" → "sent")
        queries = []
        
        # Primary searches (most specific first)
        if application.company_email:
            # If we have company email, search for it
            queries.append(f'in:sent to:{application.company_email}')
            
        if application.company_name:
            # Search by company name in subject or body
            company_clean = application.company_name.replace(" ", "").lower()
            queries.append(f'in:sent subject:"{application.company_name}"')
            queries.append(f'in:sent "{application.company_name}" learnership')
            
        # Date-based searches (if we have sent_at)
        if application.sent_at:
            date_str = application.sent_at.strftime('%Y/%m/%d')
            queries.append(f'in:sent after:{date_str} before:{date_str} (learnership OR application)')
            
        # Fallback searches
        queries.extend([
            'in:sent subject:"learnership application"',
            'in:sent "Dear Hiring Manager" learnership',
            'in:sent "application for" position'
        ])
        
        for i, query in enumerate(queries):
            print(f"    🔍 Query {i+1}/{len(queries)}: {query[:60]}...")
            
            try:
                results = service.users().messages().list(
                    userId='me',
                    q=query,
                    maxResults=10
                ).execute()
                
                messages = results.get('messages', [])
                
                if not messages:
                    print(f"    📭 No messages found")
                    continue
                
                print(f"    📧 Found {len(messages)} potential matches")
                
                # Check each message with improved scoring
                best_match = None
                best_score = 0
                
                for msg_info in messages:
                    try:
                        msg = service.users().messages().get(
                            userId='me',
                            id=msg_info['id'],
                            format='metadata',
                            metadataHeaders=['To', 'Subject', 'Date']
                        ).execute()
                        
                        score = calculate_match_score(msg, application)
                        
                        if score > best_score and score >= 5:  # Minimum threshold
                            best_score = score
                            best_match = (msg_info['id'], msg.get('threadId'), msg)
                            
                    except Exception as e:
                        print(f"    ⚠️ Error checking message: {e}")
                        continue
                
                if best_match:
                    gmail_id, thread_id, msg = best_match
                    
                    # Get message details for confirmation
                    headers = {}
                    for header in msg.get('payload', {}).get('headers', []):
                        headers[header['name'].lower()] = header['value']
                    
                    print(f"    ✅ BEST MATCH FOUND! Score: {best_score}")
                    print(f"       Subject: {headers.get('subject', '')[:50]}")
                    print(f"       To: {headers.get('to', '')[:50]}")
                    print(f"       Message ID: {gmail_id}")
                    
                    return gmail_id, thread_id
                        
            except Exception as e:
                print(f"    ⚠️ Query failed: {e}")
                continue
                
            # Rate limiting between queries
            time.sleep(0.2)
        
        return None, None
        
    except Exception as e:
        print(f"    ❌ Error searching: {e}")
        return None, None


def calculate_match_score(msg, application):
    """Calculate how well a Gmail message matches an application"""
    score = 0
    
    try:
        # Get message metadata
        internal_date = int(msg.get('internalDate', 0))
        msg_date = datetime.fromtimestamp(internal_date / 1000)
        
        headers = {}
        for header in msg.get('payload', {}).get('headers', []):
            headers[header['name'].lower()] = header['value']
        
        subject = headers.get('subject', '').lower()
        to_email = headers.get('to', '').lower()
        
        # Company email exact match (highest priority)
        if application.company_email and application.company_email.lower() in to_email:
            score += 10
            
        # Company name matching
        if application.company_name:
            company_lower = application.company_name.lower()
            if company_lower in subject:
                score += 7
            if company_lower in to_email:
                score += 8
            # Partial match
            company_words = company_lower.split()
            for word in company_words:
                if len(word) > 3 and word in subject:
                    score += 2
                    
        # Date proximity scoring
        if application.sent_at:
            time_diff = abs((msg_date - application.sent_at).total_seconds())
            if time_diff < 1800:  # Within 30 minutes
                score += 8
            elif time_diff < 3600:  # Within 1 hour
                score += 6
            elif time_diff < 86400:  # Within 1 day
                score += 4
            elif time_diff < 604800:  # Within 1 week
                score += 2
                
        # Subject keywords
        application_keywords = ['learnership', 'application', 'position', 'opportunity', 'internship']
        for keyword in application_keywords:
            if keyword in subject:
                score += 1
                
        # Learnership name matching
        if application.learnership_name:
            learnership_lower = application.learnership_name.lower()
            if learnership_lower in subject:
                score += 5
                
    except Exception as e:
        print(f"    ⚠️ Scoring error: {e}")
        
    return score


def fix_missing_gmail_ids():
    """Main function to fix missing Gmail IDs with enhanced error handling"""
    from app import app, db
    from models import Application, GoogleToken, User
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    
    with app.app_context():
        print("\n" + "=" * 70)
        print("🔧 FIXING MISSING GMAIL IDs FOR APPLICATION TRACKING")
        print("=" * 70)
        
        # Safety check
        print("\n⚠️  SAFETY WARNING:")
        print("   This script will modify your production database.")
        print("   Make sure you have a database backup!")
        
        confirm = input("\nDo you want to continue? Type 'YES' to proceed: ")
        if confirm != 'YES':
            print("Aborted by user.")
            return
            
        # Find applications without gmail_message_id
        apps_query = Application.query.filter(
            Application.gmail_message_id.is_(None)
        )
        
        # Enhanced filter options
        print(f"\n📋 Filter options:")
        print(f"   1. Process all users")
        print(f"   2. Process specific user only")
        print(f"   3. Process recent applications only (last 30 days)")
        print(f"   4. 🧪 TEST MODE: Process only first few applications")
        print(f"   5. 🎯 CUSTOM: Select specific applications by ID")
        print(f"   6. 🔧 Fix Gmail token scopes (if authentication fails)")
        
        filter_choice = input("Choose filter (1-6): ").strip()
        
        if filter_choice == '6':
            fix_gmail_token_scopes()
            return
        
        if filter_choice == '2':
            user_id = input("Enter user ID: ").strip()
            try:
                user_id = int(user_id)
                apps_query = apps_query.filter(Application.user_id == user_id)
            except:
                print("Invalid user ID")
                return
                
        elif filter_choice == '3':
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            apps_query = apps_query.filter(
                (Application.sent_at >= thirty_days_ago) | 
                (Application.submitted_at >= thirty_days_ago)
            )
            
        elif filter_choice == '4':
            limit = input("How many applications to test? (default: 5): ").strip()
            try:
                limit = int(limit) if limit else 5
            except:
                limit = 5
            apps_query = apps_query.limit(limit)
            
        elif filter_choice == '5':
            print("Enter application IDs separated by commas (e.g., 2521,2523,2525):")
            ids_input = input("Application IDs: ").strip()
            try:
                app_ids = [int(id.strip()) for id in ids_input.split(',')]
                apps_query = apps_query.filter(Application.id.in_(app_ids))
            except:
                print("Invalid application IDs")
                return
        
        apps_to_fix = apps_query.all()
        
        print(f"\n📊 Found {len(apps_to_fix)} applications to process")
        
        if not apps_to_fix:
            print("\n✅ No applications need fixing!")
            return
            
        # Show ALL applications that will be processed
        print(f"\n📋 Applications to process:")
        print(f"{'ID':<6} {'User':<6} {'Company':<25} {'Status':<12} {'Date'}")
        print("-" * 65)
        
        for app in apps_to_fix[:10]:  # Show first 10
            company = (app.company_name or "N/A")[:23]
            sent = app.sent_at.strftime("%m-%d") if app.sent_at else "N/A"
            print(f"{app.id:<6} {app.user_id:<6} {company:<25} {app.email_status:<12} {sent}")
        
        if len(apps_to_fix) > 10:
            print(f"... and {len(apps_to_fix) - 10} more applications")
        
        print("-" * 65)
        
        # Confirmation based on mode
        if filter_choice == '4':
            print(f"\n🧪 TEST MODE: Processing {len(apps_to_fix)} applications")
            final_confirm = input("Start test? Type 'TEST': ")
            if final_confirm != 'TEST':
                print("Aborted by user.")
                return
        else:
            final_confirm = input(f"\nProcess {len(apps_to_fix)} applications? Type 'PROCESS': ")
            if final_confirm != 'PROCESS':
                print("Aborted by user.")
                return
        
        # Process applications
        fixed_count = 0
        failed_count = 0
        processed_users = set()
        
        # Group by user to reuse Gmail connections
        user_apps = {}
        for app in apps_to_fix:
            if app.user_id not in user_apps:
                user_apps[app.user_id] = []
            user_apps[app.user_id].append(app)
        
        for user_id, applications in user_apps.items():
            print(f"\n{'─' * 50}")
            print(f"👤 USER {user_id} ({len(applications)} applications)")
            print(f"{'─' * 50}")
            
            try:
                # Get user and token
                user = User.query.get(user_id)
                if not user:
                    print(f"   ❌ User not found!")
                    failed_count += len(applications)
                    continue
                
                token = GoogleToken.query.filter_by(user_id=user_id).first()
                if not token:
                    print(f"   ❌ No Google token - user needs re-auth")
                    print(f"      User: {user.email}")
                    print(f"      Solution: Have user logout and login again")
                    failed_count += len(applications)
                    continue
                
                # Build Gmail service
                token_data = json.loads(token.token_json)
                creds = Credentials(
                    token=token_data.get('access_token') or token_data.get('token'),
                    refresh_token=token_data.get('refresh_token'),
                    token_uri=token_data.get('token_uri', 'https://oauth2.googleapis.com/token'),
                    client_id=token_data.get('client_id') or app.config.get('GOOGLE_CLIENT_ID'),
                    client_secret=token_data.get('client_secret') or app.config.get('GOOGLE_CLIENT_SECRET')
                )
                
                if creds.expired and creds.refresh_token:
                    from google.auth.transport.requests import Request
                    creds.refresh(Request())
                
                service = build('gmail', 'v1', credentials=creds)
                print(f"   ✅ Gmail connected for {user.email}")
                
                # Process applications for this user
                user_fixed = 0
                for i, app in enumerate(applications[:5]):  # Limit to first 5 for testing
                    print(f"\n   📄 App #{app.id} ({i+1}/{min(5, len(applications))}): {app.company_name or 'N/A'}")
                    print(f"       Date: {app.sent_at or app.submitted_at}")
                    print(f"       Status: {app.email_status}")
                    
                    gmail_id, thread_id = find_gmail_id_for_application(
                        service, app, user.email
                    )
                    
                    if gmail_id:
                        # In test mode, ask for confirmation for each match
                        if filter_choice == '4':
                            print(f"      🤔 Apply this match? (y/n/s=skip all): ", end="")
                            confirm_match = input().lower().strip()
                            if confirm_match == 's':
                                print(f"      ⏭️ Skipping remaining applications for this user")
                                failed_count += len(applications) - i
                                break
                            elif confirm_match != 'y':
                                print(f"      ⏭️ Skipped by user")
                                failed_count += 1
                                continue
                        
                        # Update application
                        app.gmail_message_id = gmail_id
                        app.gmail_thread_id = thread_id
                        
                        # Update status if needed
                        if app.email_status in ['draft', 'pending']:
                            app.email_status = 'sent'
                        
                        # Commit immediately for safety
                        db.session.commit()
                        
                        fixed_count += 1
                        user_fixed += 1
                        print(f"      ✅ FIXED! Gmail ID: {gmail_id}")
                    else:
                        failed_count += 1
                        print(f"      ⚠️ No match found")
                    
                    # Rate limiting
                    time.sleep(0.5)
                
                if len(applications) > 5:
                    print(f"   💡 Processed only first 5 applications for testing")
                    print(f"      Remaining {len(applications) - 5} applications not processed")
                    failed_count += len(applications) - 5
                
                print(f"   📊 User summary: {user_fixed}/{min(5, len(applications))} fixed")
                processed_users.add(user_id)
                
            except Exception as e:
                print(f"   ❌ User error: {e}")
                import traceback
                traceback.print_exc()
                failed_count += len(applications)
        
        # Final summary
        print("\n" + "=" * 70)
        print("📊 FINAL SUMMARY")
        print("=" * 70)
        print(f"   👥 Users processed: {len(processed_users)}")
        print(f"   ✅ Applications fixed: {fixed_count}")
        print(f"   ⚠️ Could not fix: {failed_count}")
        print(f"   📋 Total processed: {len(apps_to_fix)}")
        
        if filter_choice == '4':
            print(f"   🧪 TEST MODE completed")
            
        print("=" * 70)
        
        if fixed_count > 0:
            print("\n🎉 Success! Gmail tracking is now enabled for the fixed applications!")
            print("   You can now run your email status checker to see updates.")


def fix_gmail_token_scopes():
    """Help users fix their Gmail token scopes"""
    print("\n" + "=" * 70)
    print("🔧 GMAIL TOKEN SCOPE FIX")
    print("=" * 70)
    print("\n❌ PROBLEM: Gmail token doesn't have sufficient permissions")
    print("   The token needs these scopes:")
    print("   - https://www.googleapis.com/auth/gmail.readonly")
    print("   - https://www.googleapis.com/auth/gmail.send")
    print("   - https://www.googleapis.com/auth/gmail.modify")
    
    print("\n🔧 SOLUTIONS:")
    print("   1. Have the user log out and log back in via Google OAuth")
    print("   2. This will refresh their token with the correct scopes")
    print("   3. Or manually delete their token from the database")
    
    from app import app, db
    from models import GoogleToken, User
    
    with app.app_context():
        # Show users with tokens
        tokens = GoogleToken.query.all()
        print(f"\n👥 USERS WITH GMAIL TOKENS ({len(tokens)} total):")
        print(f"{'User ID':<8} {'Email':<30} {'Token Status'}")
        print("-" * 55)
        
        for token in tokens:
            user = User.query.get(token.user_id)
            email = user.email if user else "Unknown"
            
            try:
                token_data = json.loads(token.token_json)
                scopes = token_data.get('scopes', [])
                has_gmail = any('gmail' in scope for scope in scopes)
                status = "✅ Has Gmail" if has_gmail else "❌ Missing Gmail"
            except:
                status = "❌ Invalid"
                
            print(f"{token.user_id:<8} {email:<30} {status}")
        
        print("\n💡 To fix user 18's token:")
        print("   from models import GoogleToken")
        print("   GoogleToken.query.filter_by(user_id=18).delete()")
        print("   db.session.commit()")


def show_application_details():
    """Show details of all applications"""
    from app import app, db
    from models import Application, User
    
    with app.app_context():
        apps = Application.query.all()
        
        print("\n" + "=" * 80)
        print("📋 ALL APPLICATIONS")
        print("=" * 80)
        print(f"{'ID':<5} {'User':<8} {'Company':<20} {'Status':<12} {'Gmail':<8} {'Sent'}")
        print("-" * 80)
        
        for app in apps:
            gmail_status = "✅" if app.gmail_message_id else "❌"
            company = (app.company_name or "N/A")[:18]
            sent = app.sent_at.strftime("%Y-%m-%d") if app.sent_at else "N/A"
            
            print(f"{app.id:<5} {app.user_id:<8} {company:<20} {app.email_status:<12} {gmail_status:<8} {sent}")
        
        print("-" * 80)
        
        # Stats
        with_id = sum(1 for a in apps if a.gmail_message_id)
        without_id = sum(1 for a in apps if not a.gmail_message_id)
        
        print(f"\n📊 Stats: {with_id} with Gmail ID, {without_id} without")


if __name__ == '__main__':
    print("\n🔧 Gmail ID Fix Tool (COMPLETE VERSION)")
    print("=" * 45)
    print("1. Fix missing Gmail IDs")
    print("2. Show all applications")
    print("3. 🔧 Fix Gmail token scopes")
    print("4. Exit")
    
    choice = input("\nChoose option (1-4): ").strip()
    
    if choice == '1':
        fix_missing_gmail_ids()
    elif choice == '2':
        show_application_details()
    elif choice == '3':
        fix_gmail_token_scopes()
    else:
        print("Exiting...")