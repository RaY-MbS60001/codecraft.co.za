import sqlite3
import secrets
from datetime import datetime, timedelta

def add_test_gmail_ids():
    """Add test Gmail IDs to sent applications for testing"""
    try:
        conn = sqlite3.connect('instance/codecraft.db')
        cursor = conn.cursor()
        
        print("🔧 Adding test Gmail IDs to sent applications...")
        
        # Get all sent applications without Gmail IDs
        cursor.execute("""
            SELECT id, user_id, company_name, email_status, sent_at 
            FROM application 
            WHERE email_status = 'sent' AND gmail_message_id IS NULL
        """)
        
        sent_apps = cursor.fetchall()
        
        print(f"📋 Found {len(sent_apps)} sent applications without Gmail IDs:")
        
        updated = 0
        for app in sent_apps:
            app_id, user_id, company, status, sent_at = app
            
            # Generate realistic-looking test Gmail IDs
            message_id = f"test_{secrets.token_hex(8)}_{app_id}"
            thread_id = f"thread_{secrets.token_hex(8)}_{app_id}"
            
            # Update the application
            cursor.execute("""
                UPDATE application 
                SET gmail_message_id = ?, 
                    gmail_thread_id = ?,
                    email_status = 'sent'
                WHERE id = ?
            """, (message_id, thread_id, app_id))
            
            print(f"  ✅ App {app_id} ({company}): Added Gmail ID {message_id[:20]}...")
            updated += 1
        
        conn.commit()
        conn.close()
        
        print(f"\n🎉 Successfully added Gmail IDs to {updated} applications!")
        print("Now you can test the Gmail status checker!")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    add_test_gmail_ids()
    