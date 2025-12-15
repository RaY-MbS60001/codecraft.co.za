import os
import sqlite3
from pathlib import Path

def reset_database():
    """Drop all tables and reset database"""
    
    db_path = "instance/codecraft.db"
    backup_path = f"instance/backup_before_reset_{int(time.time())}.db"
    
    print("🗄️ DATABASE RESET UTILITY")
    print("=" * 50)
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        return
    
    print(f"📊 Database size: {os.path.getsize(db_path):,} bytes")
    
    # Create backup first
    try:
        import shutil
        shutil.copy2(db_path, backup_path)
        print(f"💾 Backup created: {backup_path}")
    except Exception as e:
        print(f"⚠️ Backup failed: {e}")
        proceed = input("Continue without backup? (y/N): ")
        if proceed.lower() != 'y':
            return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = cursor.fetchall()
        
        print(f"\n📋 Found {len(tables)} tables to drop:")
        for table in tables:
            print(f"   • {table[0]}")
        
        print(f"\n⚠️ WARNING: This will permanently delete ALL data!")
        confirm = input("Type 'DELETE ALL TABLES' to proceed: ")
        
        if confirm != "DELETE ALL TABLES":
            print("❌ Operation cancelled")
            return
        
        # Drop all tables
        print("\n🗑️ Dropping tables...")
        
        # Disable foreign key constraints
        cursor.execute("PRAGMA foreign_keys = OFF")
        
        dropped = 0
        for table in tables:
            table_name = table[0]
            try:
                cursor.execute(f"DROP TABLE IF EXISTS `{table_name}`")
                print(f"   ✅ Dropped: {table_name}")
                dropped += 1
            except Exception as e:
                print(f"   ❌ Failed to drop {table_name}: {e}")
        
        # Re-enable foreign key constraints
        cursor.execute("PRAGMA foreign_keys = ON")
        
        conn.commit()
        conn.close()
        
        print(f"\n🎉 Successfully dropped {dropped} tables!")
        print(f"📊 New database size: {os.path.getsize(db_path):,} bytes")
        print(f"💾 Backup saved as: {backup_path}")
        print(f"\n🔄 Restart your Flask app to recreate tables")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    import time
    reset_database()