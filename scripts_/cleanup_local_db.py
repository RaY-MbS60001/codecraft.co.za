import sqlite3
from pathlib import Path

# Path to your local SQLite database
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "instance" / "codecraft.db"

def cleanup_local_database():
    """Remove obsolete tables from local SQLite database"""
    
    # Tables to remove (obsolete/unused)
    tables_to_remove = [
        'email_application',
        'learnership_applications',
        'learnership_emails', 
        'learnership_email',
        'learnership',
        'application_document'
    ]
    
    # Tables to keep (essential)
    essential_tables = [
        'application',
        'user',
        'document', 
        'google_token',
        'premium_transactions',
        'sqlite_sequence'  # SQLite system table
    ]
    
    if not DB_PATH.exists():
        print(f"❌ Database not found at: {DB_PATH}")
        return
    
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        print("🧹 LOCAL DATABASE CLEANUP")
        print("=" * 60)
        
        # Get current tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        current_tables = [row[0] for row in cursor.fetchall()]
        
        print("📋 Current Tables:")
        for table in current_tables:
            if table in essential_tables:
                print(f"   ✅ KEEP: {table}")
            elif table in tables_to_remove:
                print(f"   ❌ REMOVE: {table}")
            else:
                print(f"   ❓ UNKNOWN: {table}")
        
        # Get row counts before deletion
        print(f"\n📊 Data in tables to be removed:")
        for table in tables_to_remove:
            if table in current_tables:
                try:
                    cursor.execute(f'SELECT COUNT(*) FROM "{table}";')
                    count = cursor.fetchone()[0]
                    print(f"   • {table}: {count} rows")
                except:
                    print(f"   • {table}: Error getting count")
        
        # Confirm deletion
        tables_to_delete = [t for t in tables_to_remove if t in current_tables]
        if not tables_to_delete:
            print("✅ No obsolete tables found! Database is already clean.")
            return
            
        print(f"\n⚠️  This will permanently delete {len(tables_to_delete)} tables from LOCAL database!")
        confirm = input("Type 'DELETE' to confirm: ")
        
        if confirm != 'DELETE':
            print("❌ Cleanup cancelled.")
            return
        
        print("\n🗑️  Starting table removal...")
        
        # Remove tables
        removed_count = 0
        for table in tables_to_delete:
            try:
                print(f"   🗑️  Dropping table: {table}")
                cursor.execute(f'DROP TABLE IF EXISTS "{table}";')
                print(f"   ✅ Successfully removed: {table}")
                removed_count += 1
            except Exception as e:
                print(f"   ❌ Error removing {table}: {e}")
        
        # Verify cleanup
        print(f"\n🔍 Verifying cleanup...")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        remaining_tables = [row[0] for row in cursor.fetchall()]
        
        print(f"📋 Remaining tables ({len(remaining_tables)}):")
        for table in remaining_tables:
            if table != 'sqlite_sequence':  # Skip system table for count
                cursor.execute(f'SELECT COUNT(*) FROM "{table}";')
                count = cursor.fetchone()[0]
                status = "🟢" if count > 0 else "🔴"
                print(f"   {status} {table} ({count} rows)")
            else:
                print(f"   ⚙️  {table} (system table)")
        
        # Commit changes and close
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"\n🎉 LOCAL CLEANUP COMPLETED!")
        print(f"✅ Removed {removed_count} obsolete tables")
        print(f"✅ Kept {len(remaining_tables)} essential tables")
        print("🚀 Your local database is now clean and optimized!")
        
    except Exception as e:
        print(f"❌ Cleanup failed: {e}")

if __name__ == "__main__":
    cleanup_local_database()