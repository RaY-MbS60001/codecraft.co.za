# fix_invalid_gmail_ids.py
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def fix_invalid_gmail_ids():
    # Import here to avoid circular import issues
    from app import app
    from models import db, Application
    
    with app.app_context():
        print("🔧 Starting Gmail ID cleanup...")
        
        # Find applications with email-like Gmail message IDs (invalid)
        invalid_apps = Application.query.filter(
            Application.gmail_message_id.like('%@gmail.com')
        ).all()
        
        print(f"📋 Found {len(invalid_apps)} applications with invalid Gmail message IDs")
        
        if invalid_apps:
            print("\n❌ Applications with invalid Gmail IDs:")
            for app_record in invalid_apps:
                print(f"   - App #{app_record.id}: {app_record.company_name} -> {app_record.gmail_message_id}")
        
        # Also find other potentially invalid IDs (not hex format)
        all_apps_with_gmail_id = Application.query.filter(
            Application.gmail_message_id.isnot(None)
        ).all()
        
        other_invalid = []
        valid_count = 0
        
        for app_record in all_apps_with_gmail_id:
            gmail_id = app_record.gmail_message_id
            # Valid Gmail message IDs are typically hex strings (letters a-f and numbers 0-9)
            if '@' in gmail_id or len(gmail_id) < 10 or not all(c in '0123456789abcdef' for c in gmail_id.lower()):
                if '@gmail.com' not in gmail_id:  # Don't double count
                    other_invalid.append(app_record)
            else:
                valid_count += 1
        
        print(f"\n📊 Gmail ID Status:")
        print(f"   ✅ Valid Gmail IDs: {valid_count}")
        print(f"   ❌ Invalid email-like IDs: {len(invalid_apps)}")
        print(f"   ⚠️ Other invalid IDs: {len(other_invalid)}")
        
        if other_invalid:
            print(f"\n⚠️ Other potentially invalid Gmail IDs:")
            for app_record in other_invalid[:5]:  # Show first 5
                print(f"   - App #{app_record.id}: {app_record.company_name} -> {app_record.gmail_message_id}")
            if len(other_invalid) > 5:
                print(f"   ... and {len(other_invalid) - 5} more")
        
        # Ask for confirmation
        total_to_fix = len(invalid_apps) + len(other_invalid)
        if total_to_fix > 0:
            print(f"\n🔄 This will set {total_to_fix} invalid Gmail message IDs to NULL")
            confirm = input("Continue? (y/N): ").strip().lower()
            
            if confirm in ['y', 'yes']:
                # Fix email-like IDs
                for app_record in invalid_apps:
                    print(f"   Fixing #{app_record.id}: {app_record.company_name}")
                    app_record.gmail_message_id = None
                    app_record.gmail_thread_id = None
                    app_record.email_status = 'failed'  # Mark as failed since we can't track
                
                # Fix other invalid IDs
                for app_record in other_invalid:
                    print(f"   Fixing #{app_record.id}: {app_record.company_name}")
                    app_record.gmail_message_id = None
                    app_record.gmail_thread_id = None
                    app_record.email_status = 'failed'  # Mark as failed since we can't track
                
                try:
                    db.session.commit()
                    print(f"✅ Successfully fixed {total_to_fix} applications!")
                    print("💡 These applications will need to be re-sent to be tracked properly.")
                except Exception as e:
                    db.session.rollback()
                    print(f"❌ Error saving changes: {e}")
            else:
                print("❌ Cleanup cancelled")
        else:
            print("✅ All Gmail message IDs are valid!")

if __name__ == "__main__":
    fix_invalid_gmail_ids()