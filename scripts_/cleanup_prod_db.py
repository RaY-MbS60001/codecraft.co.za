import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

POSTGRESQL_URL = (
    "postgresql://codecraftco_db_user:84u1KfAY4jHElF1ISEVw4YNbtZM51691@"
    "dpg-d1lknv6r433s73drf130-a.oregon-postgres.render.com:5432/"
    "codecraftco_db"
)

def cleanup_production_database():
    """Remove obsolete tables from production database"""
    
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
        'premium_transactions'
    ]
    
    try:
        conn = psycopg2.connect(POSTGRESQL_URL)
        cursor = conn.cursor()
        
        print("🧹 PRODUCTION DATABASE CLEANUP")
        print("=" * 60)
        
        # First, show current tables
        cursor.execute("""
            SELECT table_name, 
                   (SELECT COUNT(*) FROM information_schema.tables t2 
                    WHERE t2.table_name = t1.table_name AND t2.table_schema = 'public') as exists
            FROM information_schema.tables t1
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        
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
        print(f"\n⚠️  This will permanently delete {len([t for t in tables_to_remove if t in current_tables])} tables from PRODUCTION!")
        confirm = input("Type 'DELETE' to confirm: ")
        
        if confirm != 'DELETE':
            print("❌ Cleanup cancelled.")
            return
        
        print("\n🗑️  Starting table removal...")
        
        # Remove tables in safe order (handle foreign key dependencies)
        removal_order = [
            'email_application',      # Remove first (might reference other tables)
            'learnership_applications',
            'application_document',   # Remove before document dependencies
            'learnership_emails',
            'learnership_email', 
            'learnership'            # Remove last (might be referenced)
        ]
        
        removed_count = 0
        for table in removal_order:
            if table in current_tables:
                try:
                    print(f"   🗑️  Dropping table: {table}")
                    cursor.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE;')
                    conn.commit()
                    print(f"   ✅ Successfully removed: {table}")
                    removed_count += 1
                except Exception as e:
                    print(f"   ❌ Error removing {table}: {e}")
                    conn.rollback()
        
        # Verify cleanup
        print(f"\n🔍 Verifying cleanup...")
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        
        remaining_tables = [row[0] for row in cursor.fetchall()]
        
        print(f"📋 Remaining tables ({len(remaining_tables)}):")
        for table in remaining_tables:
            cursor.execute(f'SELECT COUNT(*) FROM "{table}";')
            count = cursor.fetchone()[0]
            status = "🟢" if count > 0 else "🔴"
            print(f"   {status} {table} ({count} rows)")
        
        cursor.close()
        conn.close()
        
        print(f"\n🎉 PRODUCTION CLEANUP COMPLETED!")
        print(f"✅ Removed {removed_count} obsolete tables")
        print(f"✅ Kept {len(remaining_tables)} essential tables")
        print("🚀 Your production database is now clean and optimized!")
        
    except Exception as e:
        print(f"❌ Cleanup failed: {e}")

if __name__ == "__main__":
    cleanup_production_database()