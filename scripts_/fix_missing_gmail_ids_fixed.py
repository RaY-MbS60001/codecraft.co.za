# scripts_/fix_missing_gmail_ids_fixed.py
"""
FIXED: Complete script with proper error handling for database issues
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
import json
import time


def fix_gmail_token_scopes():
    """Help users fix their Gmail token scopes with better error handling"""
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
        print(f"{'User ID':<8} {'Email':<35} {'Token Status'}")
        print("-" * 65)
        
        valid_tokens = 0
        invalid_tokens = 0
        
        for token in tokens:
            try:
                # Handle NULL user_id gracefully
                if token.user_id is None:
                    print(f"{'NULL':<8} {'ORPHANED TOKEN':<35} {'❌ Invalid - No User'}")
                    invalid_tokens += 1
                    continue
                
                user = User.query.filter_by(id=token.user_id).first()
                email = user.email if user else f"USER {token.user_id} NOT FOUND"
                
                try:
                    token_data = json.loads(token.token_json)
                    scopes = token_data.get('scopes', [])
                    has_gmail = any('gmail' in scope for scope in scopes)
                    
                    if has_gmail:
                        # Check specific scopes
                        required_scopes = [
                            'https://www.googleapis.com/auth/gmail.readonly',
                            'https://www.googleapis.com/auth/gmail.send',
                            'https://www.googleapis.com/auth/gmail.modify'
                        ]
                        
                        has_all_scopes = all(scope in scopes for scope in required_scopes)
                        status = "✅ Full Gmail Access" if has_all_scopes else "⚠️ Partial Gmail"
                    else:
                        status = "❌ No Gmail Access"
                    
                    valid_tokens += 1
                except Exception as e:
                    status = f"❌ Invalid JSON: {str(e)[:20]}"
                    invalid_tokens += 1
                    
                print(f"{token.user_id:<8} {email[:33]:<35} {status}")
                
            except Exception as e:
                print(f"{'ERROR':<8} {'PROCESSING ERROR':<35} {str(e)[:25]}")
                invalid_tokens += 1
        
        print("-" * 65)
        print(f"📊 Summary: {valid_tokens} valid, {invalid_tokens} invalid tokens")
        
        # Check if user 18 has a token
        user_18_token = GoogleToken.query.filter_by(user_id=18).first()
        user_18 = User.query.filter_by(id=18).first()
        
        print(f"\n🎯 USER 18 SPECIFIC CHECK:")
        if user_18:
            print(f"   User 18 exists: {user_18.email}")
            if user_18_token:
                print(f"   ✅ Has token")
                try:
                    token_data = json.loads(user_18_token.token_json)
                    scopes = token_data.get('scopes', [])
                    print(f"   📋 Token scopes: {len(scopes)} total")
                    for scope in scopes:
                        print(f"      - {scope}")
                except:
                    print(f"   ❌ Token data is corrupted")
            else:
                print(f"   ❌ No token found!")
                print(f"   💡 Solution: Have user login via Google OAuth")
        else:
            print(f"   ❌ User 18 does not exist!")
            
        # Clean up suggestions
        print(f"\n🧹 CLEANUP SUGGESTIONS:")
        if invalid_tokens > 0:
            print(f"   1. Delete {invalid_tokens} invalid/orphaned tokens:")
            print(f"      GoogleToken.query.filter(GoogleToken.user_id.is_(None)).delete()")
            
        print(f"   2. For users with missing Gmail scopes:")
        print(f"      Have them logout and login again via /login/google")
        
        print(f"   3. To delete user 18's token specifically:")
        print(f"      GoogleToken.query.filter_by(user_id=18).delete()")


def show_application_details():
    """Show details of all applications with better error handling"""
    from app import app, db
    from models import Application, User
    
    with app.app_context():
        # Check user 18 specifically
        user_18 = User.query.filter_by(id=18).first()
        if user_18:
            print(f"\n👤 USER 18: {user_18.email}")
            user_18_apps = Application.query.filter_by(user_id=18).all()
            print(f"   Applications: {len(user_18_apps)}")
            
            # Show recent applications for user 18
            recent_apps = Application.query.filter_by(user_id=18).order_by(Application.id.desc()).limit(10).all()
            print(f"\n📋 RECENT APPLICATIONS FOR USER 18:")
            print(f"{'ID':<6} {'Company':<25} {'Status':<12} {'Gmail':<8} {'Date'}")
            print("-" * 65)
            
            for app in recent_apps:
                gmail_status = "✅" if app.gmail_message_id else "❌"
                company = (app.company_name or "N/A")[:23]
                sent = app.sent_at.strftime("%m-%d") if app.sent_at else "N/A"
                
                print(f"{app.id:<6} {company:<25} {app.email_status:<12} {gmail_status:<8} {sent}")
        else:
            print("\n❌ USER 18 NOT FOUND!")
        
        # Overall stats
        apps = Application.query.all()
        with_id = sum(1 for a in apps if a.gmail_message_id)
        without_id = sum(1 for a in apps if not a.gmail_message_id)
        
        print(f"\n📊 OVERALL STATS:")
        print(f"   Total applications: {len(apps)}")
        print(f"   With Gmail tracking: {with_id}")
        print(f"   Without Gmail tracking: {without_id}")


def clean_database():
    """Clean up database issues"""
    from app import app, db
    from models import GoogleToken, User
    
    with app.app_context():
        print("\n🧹 DATABASE CLEANUP")
        print("=" * 40)
        
        # Find orphaned tokens
        orphaned = GoogleToken.query.filter(GoogleToken.user_id.is_(None)).all()
        print(f"Found {len(orphaned)} orphaned tokens")
        
        if orphaned:
            confirm = input("Delete orphaned tokens? (y/n): ")
            if confirm.lower() == 'y':
                for token in orphaned:
                    db.session.delete(token)
                db.session.commit()
                print("✅ Orphaned tokens deleted")
        
        # Find tokens for non-existent users
        all_tokens = GoogleToken.query.all()
        invalid_user_tokens = []
        
        for token in all_tokens:
            if token.user_id is not None:
                user = User.query.filter_by(id=token.user_id).first()
                if not user:
                    invalid_user_tokens.append(token)
        
        print(f"Found {len(invalid_user_tokens)} tokens for non-existent users")
        
        if invalid_user_tokens:
            for token in invalid_user_tokens:
                print(f"  Token for missing user {token.user_id}")
            
            confirm = input("Delete these tokens? (y/n): ")
            if confirm.lower() == 'y':
                for token in invalid_user_tokens:
                    db.session.delete(token)
                db.session.commit()
                print("✅ Invalid user tokens deleted")


if __name__ == '__main__':
    print("\n🔧 Gmail ID Fix Tool (FIXED VERSION)")
    print("=" * 45)
    print("1. Fix missing Gmail IDs")
    print("2. Show all applications")
    print("3. 🔧 Fix Gmail token scopes")
    print("4. 🧹 Clean database")
    print("5. Exit")
    
    choice = input("\nChoose option (1-5): ").strip()
    
    if choice == '1':
        # fix_missing_gmail_ids()  # Commented out for now
        print("Feature temporarily disabled - fix token issues first")
    elif choice == '2':
        show_application_details()
    elif choice == '3':
        fix_gmail_token_scopes()
    elif choice == '4':
        clean_database()
    else:
        print("Exiting...")