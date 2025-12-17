import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# Your production database URL
POSTGRESQL_URL = (
    "postgresql://codecraftco_db_user:84u1KfAY4jHElF1ISEVw4YNbtZM51691@"
    "dpg-d1lknv6r433s73drf130-a.oregon-postgres.render.com:5432/"
    "codecraftco_db"
)

def connect_to_prod():
    """Connect to production PostgreSQL database"""
    try:
        conn = psycopg2.connect(POSTGRESQL_URL)
        return conn
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return None

def get_table_list(conn):
    """Get list of all tables in production"""
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT table_name, table_type 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """)
            return cur.fetchall()
    except Exception as e:
        print(f"❌ Error getting tables: {e}")
        return []

def get_table_structure(conn, table_name):
    """Get detailed structure of a specific table"""
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    column_name,
                    data_type,
                    is_nullable,
                    column_default,
                    character_maximum_length
                FROM information_schema.columns 
                WHERE table_name = %s AND table_schema = 'public'
                ORDER BY ordinal_position;
            """, (table_name,))
            return cur.fetchall()
    except Exception as e:
        print(f"❌ Error getting table structure: {e}")
        return []

def get_table_row_count(conn, table_name):
    """Get row count for a table"""
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {table_name};")
            return cur.fetchone()[0]
    except Exception as e:
        return 0

def main():
    print("🗄️ PRODUCTION PostgreSQL DATABASE INSPECTOR")
    print("=" * 60)
    
    conn = connect_to_prod()
    if not conn:
        return
    
    print("✅ Connected to production database!")
    
    # Get all tables
    tables = get_table_list(conn)
    
    print("\n📋 TABLES IN PRODUCTION DATABASE:")
    print("-" * 60)
    print(f"{'TABLE NAME':<25} {'ROWS':<10} {'STATUS'}")
    print("-" * 60)
    
    for table in tables:
        table_name = table['table_name']
        row_count = get_table_row_count(conn, table_name)
        status = "🟢 Has data" if row_count > 0 else "🔴 EMPTY"
        print(f"{table_name:<25} {row_count:<10} {status}")
    
    print("-" * 60)
    
    # Interactive mode
    while True:
        print("\n🤔 WHAT WOULD YOU LIKE TO DO?")
        print("1. 📋 View table structure")
        print("2. 📊 Compare with local database")
        print("3. 🔄 Refresh table list")
        print("4. 🚪 Exit")
        
        choice = input("\nEnter choice (1-4): ").strip()
        
        if choice == "1":
            table_name = input("Enter table name: ").strip()
            structure = get_table_structure(conn, table_name)
            
            if structure:
                print(f"\n📊 STRUCTURE OF '{table_name}':")
                print("-" * 80)
                print(f"{'COLUMN':<25} {'TYPE':<20} {'NULL':<10} {'DEFAULT'}")
                print("-" * 80)
                for col in structure:
                    nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
                    default = col['column_default'] or ""
                    print(f"{col['column_name']:<25} {col['data_type']:<20} {nullable:<10} {default}")
                print("-" * 80)
            else:
                print(f"❌ Table '{table_name}' not found or error occurred")
        
        elif choice == "2":
            print("\n🔍 TABLES MISSING IN PRODUCTION:")
            missing_tables = []
            
            # Tables that should exist based on your dev DB
            expected_tables = [
                'application', 'application_document', 'document', 
                'email_application', 'google_token', 'learnership',
                'learnership_applications', 'learnership_emails', 
                'premium_transactions', 'user'
            ]
            
            existing_table_names = [t['table_name'] for t in tables]
            
            for expected in expected_tables:
                if expected not in existing_table_names:
                    missing_tables.append(expected)
                    print(f"❌ MISSING: {expected}")
            
            if not missing_tables:
                print("✅ All expected tables exist!")
        
        elif choice == "3":
            tables = get_table_list(conn)
            print("🔄 Table list refreshed!")
        
        elif choice == "4":
            break
        else:
            print("❌ Invalid choice!")
    
    conn.close()
    print("👋 Disconnected from production database")

if __name__ == "__main__":
    main()