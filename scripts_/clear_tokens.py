import sqlite3
import sys
import os

# Add the parent directory to the path to import models
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def clear_gmail_tokens():
    """Clear Gmail tokens directly from database"""
    try:
        # Connect to database
        conn = sqlite3.connect('instance/codecraft.db')
        cursor = conn.cursor()
        
        print("🔍 Checking for Gmail tokens...")
        
        # Check existing tokens
        cursor.execute("SELECT COUNT(*) FROM google_token")
        total_tokens = cursor.fetchone()[0]
        
        if total_tokens == 0:
            print("ℹ️ No Gmail tokens found in database")
            return
        
        print(f"📋 Found {total_tokens} Gmail token(s)")
        
        # Show token details
        cursor.execute("SELECT id, user_id, refreshed_at FROM google_token")
        tokens = cursor.fetchall()
        
        print("\n🗃️ Current tokens:")
        for token_id, user_id, refreshed_at in tokens:
            print(f"   Token {token_id}: User {user_id}, Last refreshed: {refreshed_at}")
        
        # Ask for confirmation
        print(f"\n⚠️ This will delete ALL {total_tokens} Gmail tokens.")
        print("Users will need to reconnect Gmail with new permissions.")
        
        confirm = input("Type 'DELETE' to proceed: ")
        
        if confirm != 'DELETE':
            print("❌ Operation cancelled")
            return
        
        # Delete all tokens
        cursor.execute("DELETE FROM google_token")
        deleted_count = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        print(f"✅ Successfully deleted {deleted_count} Gmail token(s)")
        print("🔄 Users can now reconnect Gmail with updated scopes")
        
    except Exception as e:
        print(f"❌ Error: {e}")

def clear_specific_user_token():
    """Clear Gmail token for specific user"""
    try:
        conn = sqlite3.connect('instance/codecraft.db')
        cursor = conn.cursor()
        
        # Show all users with tokens
        cursor.execute("""
            SELECT gt.user_id, u.email, u.full_name 
            FROM google_token gt
            LEFT JOIN user u ON gt.user_id = u.id
        """)
        users = cursor.fetchall()
        
        if not users:
            print("ℹ️ No users with Gmail tokens found")
            return
        
        print("\n👥 Users with Gmail tokens:")
        for user_id, email, name in users:
            print(f"   User {user_id}: {email} ({name or 'No name'})")
        
        user_id = input("\nEnter user ID to clear token for: ").strip()
        
        if not user_id.isdigit():
            print("❌ Invalid user ID")
            return
        
        user_id = int(user_id)
        
        # Check if user has token
        cursor.execute("SELECT COUNT(*) FROM google_token WHERE user_id = ?", (user_id,))
        if cursor.fetchone()[0] == 0:
            print(f"❌ No token found for user {user_id}")
            return
        
        # Delete specific user's token
        cursor.execute("DELETE FROM google_token WHERE user_id = ?", (user_id,))
        
        if cursor.rowcount > 0:
            conn.commit()
            print(f"✅ Successfully deleted Gmail token for user {user_id}")
        else:
            print(f"❌ No token was deleted for user {user_id}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("🗑️ Gmail Token Cleaner")
    print("=" * 50)
    
    print("1. Clear ALL Gmail tokens")
    print("2. Clear token for specific user")
    print("3. Exit")
    
    choice = input("\nEnter your choice (1-3): ").strip()
    
    if choice == "1":
        clear_gmail_tokens()
    elif choice == "2":
        clear_specific_user_token()
    elif choice == "3":
        print("👋 Goodbye!")
    else:
        print("❌ Invalid choice")