import sqlite3
from pathlib import Path

# Path to your local SQLite database
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "instance" / "codecraft.db"

def add_company_email_column():
    """Add company_email column to Application table"""
    
    if not DB_PATH.exists():
        print(f"❌ Database not found at: {DB_PATH}")
        return
    
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        print("🔧 ADDING company_email COLUMN TO APPLICATION TABLE")
        print("=" * 60)
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(application);")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'company_email' in columns:
            print("✅ company_email column already exists!")
            return
        
        print("📝 Adding company_email column...")
        
        # Add the column
        cursor.execute('ALTER TABLE application ADD COLUMN company_email VARCHAR(255);')
        
        print("✅ Column added successfully!")
        
        # Set default email values for existing applications
        print("📝 Setting default email values for existing applications...")
        
        # You can set a default email or leave null for now
        # Option 1: Set a placeholder email
        cursor.execute("UPDATE application SET company_email = 'unknown@company.com' WHERE company_email IS NULL;")
        
        # Option 2: Or leave as NULL and handle in code
        # (Do nothing - column allows NULL)
        
        print("✅ Default values set!")
        
        # Verify the addition
        cursor.execute("PRAGMA table_info(application);")
        columns_after = cursor.fetchall()
        
        print("\n📋 Current application table columns:")
        for col in columns_after:
            column_name = col[1]
            column_type = col[2]
            is_nullable = "NULL" if col[3] == 0 else "NOT NULL"
            default_val = col[4] if col[4] else "No default"
            
            status = "🆕" if column_name == 'company_email' else "  "
            print(f"   {status} {column_name} ({column_type}) - {is_nullable} - Default: {default_val}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("\n🎉 MIGRATION COMPLETED!")
        print("✅ company_email column added to application table")
        print("🚀 Your app should now work without database errors!")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")

if __name__ == "__main__":
    add_company_email_column()