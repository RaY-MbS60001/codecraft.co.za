import sqlite3
import os
from pathlib import Path

# Path to your local SQLite database
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "instance" / "codecraft.db"

def update_local_database():
    """Update local SQLite database to match production structure"""
    
    if not DB_PATH.exists():
        print(f"❌ Database not found at: {DB_PATH}")
        return
    
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        print("🔧 UPDATING LOCAL DATABASE TO MATCH PRODUCTION")
        print("=" * 60)
        
        # Step 1: Rename learnership_emails table to learnership_email
        print("📝 Step 1: Checking table names...")
        
        # Check if learnership_emails exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='learnership_emails';")
        has_learnership_emails = cursor.fetchone() is not None
        
        # Check if learnership_email exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='learnership_email';")
        has_learnership_email = cursor.fetchone() is not None
        
        if has_learnership_emails and not has_learnership_email:
            print("   🔄 Renaming learnership_emails to learnership_email...")
            
            # Create new table with correct name
            cursor.execute('''
                CREATE TABLE learnership_email AS 
                SELECT * FROM learnership_emails;
            ''')
            
            # Drop old table
            cursor.execute('DROP TABLE learnership_emails;')
            print("   ✅ Table renamed successfully!")
            
        elif has_learnership_email:
            print("   ✅ Table learnership_email already exists!")
            
            # If both exist, we need to merge data and drop the old one
            if has_learnership_emails:
                print("   🔄 Both tables exist, merging data...")
                cursor.execute('''
                    INSERT OR IGNORE INTO learnership_email 
                    SELECT * FROM learnership_emails;
                ''')
                cursor.execute('DROP TABLE learnership_emails;')
                print("   ✅ Data merged and old table dropped!")
        
        # Step 2: Check and update user table structure
        print("\n📝 Step 2: Checking user table structure...")
        
        # Get current user table columns
        cursor.execute("PRAGMA table_info(user);")
        columns = {row[1]: row for row in cursor.fetchall()}
        
        premium_columns = {
            'is_premium': 'BOOLEAN DEFAULT FALSE',
            'premium_expires': 'DATETIME',
            'daily_applications_used': 'INTEGER DEFAULT 0',
            'last_application_date': 'DATE',
            'premium_activated_by': 'INTEGER',
            'premium_activated_at': 'DATETIME'
        }
        
        missing_columns = []
        for col_name, col_def in premium_columns.items():
            if col_name not in columns:
                missing_columns.append((col_name, col_def))
        
        if missing_columns:
            print(f"   🔄 Adding {len(missing_columns)} missing premium columns...")
            for col_name, col_def in missing_columns:
                try:
                    cursor.execute(f'ALTER TABLE user ADD COLUMN {col_name} {col_def};')
                    print(f"   ✅ Added column: {col_name}")
                except Exception as e:
                    print(f"   ⚠️  Warning for {col_name}: {e}")
        else:
            print("   ✅ All premium columns already exist!")
        
        # Step 3: Update existing users with default values
        print("\n📝 Step 3: Setting default values for existing users...")
        
        update_commands = [
            "UPDATE user SET is_premium = FALSE WHERE is_premium IS NULL;",
            "UPDATE user SET daily_applications_used = 0 WHERE daily_applications_used IS NULL;",
            "UPDATE user SET last_application_date = date('now') WHERE last_application_date IS NULL;"
        ]
        
        for cmd in update_commands:
            cursor.execute(cmd)
        
        print("   ✅ Default values set!")
        
        # Step 4: Check premium_transactions table
        print("\n📝 Step 4: Checking premium_transactions table...")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='premium_transactions';")
        
        if cursor.fetchone():
            print("   ✅ premium_transactions table exists!")
        else:
            print("   🔄 Creating premium_transactions table...")
            cursor.execute('''
                CREATE TABLE premium_transactions (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    transaction_type VARCHAR(50) NOT NULL,
                    amount FLOAT,
                    duration_days INTEGER NOT NULL,
                    activated_by_admin INTEGER,
                    created_at DATETIME,
                    notes TEXT,
                    FOREIGN KEY (user_id) REFERENCES user(id),
                    FOREIGN KEY (activated_by_admin) REFERENCES user(id)
                );
            ''')
            print("   ✅ premium_transactions table created!")
        
        # Step 5: Verify final structure
        print("\n🔍 Verifying final database structure...")
        
        # Check tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        tables = [row[0] for row in cursor.fetchall()]
        
        expected_tables = [
            'application', 'application_document', 'document', 
            'email_application', 'google_token', 'learnership',
            'learnership_applications', 'learnership_email',  # Note: singular
            'premium_transactions', 'sqlite_sequence', 'user'
        ]
        
        print("📋 Current tables:")
        for table in tables:
            status = "✅" if table in expected_tables else "⚠️"
            print(f"   {status} {table}")
        
        # Check user table columns
        cursor.execute("PRAGMA table_info(user);")
        user_columns = [row[1] for row in cursor.fetchall()]
        
        required_premium_cols = ['is_premium', 'premium_expires', 'daily_applications_used', 
                               'last_application_date', 'premium_activated_by', 'premium_activated_at']
        
        print("\n👤 User table premium columns:")
        for col in required_premium_cols:
            status = "✅" if col in user_columns else "❌"
            print(f"   {status} {col}")
        
        # Commit changes
        conn.commit()
        cursor.close()
        conn.close()
        
        print("\n🎉 LOCAL DATABASE UPDATE COMPLETED!")
        print("🚀 Your local database now matches production structure!")
        
    except Exception as e:
        print(f"❌ Error updating database: {e}")

if __name__ == "__main__":
    print("🗄️ LOCAL DATABASE STRUCTURE UPDATE")
    print("=" * 60)
    
    response = input("⚠️  This will update your local database structure. Continue? (y/N): ")
    if response.lower() == 'y':
        update_local_database()
    else:
        print("❌ Update cancelled.")