import psycopg2
from psycopg2 import sql

# ============================================================
# IMPORT DATA FROM SEPARATE FILE
# ============================================================
from learnership_emails import learnership_email_data

# ============================================================
# DATABASE CONNECTION
# ============================================================

DB_CONFIG = {
    "host": "dpg-d1lknv6r433s73drf130-a.oregon-postgres.render.com",
    "port": "5432",
    "database": "codecraftco_db",
    "user": "codecraftco_db_user",
    "password": "84u1KfAY4jHElF1ISEVw4YNbtZM51691",  # 🔐 ROTATE THIS!
    "sslmode": "require"
}

# Table name
TABLE_NAME = "learnership_email"  # <-- UPDATE if different

# ============================================================
# FUNCTIONS
# ============================================================

def connect_db():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        print("✅ Connected to production database!")
        return conn
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return None


def discover_tables_with_counts(conn):
    """List all tables with row counts - highlights empty tables"""
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name;
    """)
    tables = cursor.fetchall()
    
    print("\n📋 TABLES IN YOUR DATABASE:")
    print("=" * 60)
    print(f"{'TABLE NAME':<35} {'ROWS':<10} {'STATUS'}")
    print("-" * 60)
    
    empty_tables = []
    non_empty_tables = []
    
    for table in tables:
        table_name = table[0]
        try:
            cursor.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table_name)))
            count = cursor.fetchone()[0]
            
            if count == 0:
                status = "🔴 EMPTY"
                empty_tables.append(table_name)
            else:
                status = "🟢 Has data"
                non_empty_tables.append((table_name, count))
            
            print(f"  {table_name:<33} {count:<10} {status}")
        except Exception as e:
            print(f"  {table_name:<33} {'?':<10} ⚠️ Error: {e}")
    
    print("-" * 60)
    
    print(f"\n📊 SUMMARY:")
    print(f"   Total tables: {len(tables)}")
    print(f"   🟢 With data: {len(non_empty_tables)}")
    print(f"   🔴 Empty: {len(empty_tables)}")
    
    if empty_tables:
        print(f"\n🔴 EMPTY TABLES:")
        for t in empty_tables:
            print(f"   • {t}")
    
    if non_empty_tables:
        print(f"\n🟢 TABLES WITH DATA:")
        for t, count in non_empty_tables:
            print(f"   • {t} ({count} rows)")
    
    print("=" * 60)
    
    return tables, empty_tables, non_empty_tables


def show_table_structure(conn, table_name):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns 
        WHERE table_name = %s
        ORDER BY ordinal_position;
    """, (table_name,))
    columns = cursor.fetchall()
    
    print(f"\n📊 STRUCTURE OF '{table_name}':")
    print("-" * 50)
    if columns:
        for col in columns:
            print(f"  • {col[0]} ({col[1]}) {'NULL' if col[2] == 'YES' else 'NOT NULL'}")
    else:
        print(f"  ❌ Table '{table_name}' not found!")
    print("-" * 50)
    return columns


def show_existing_data(conn, table_name, limit=10):
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = %s
            ORDER BY ordinal_position;
        """, (table_name,))
        columns = [col[0] for col in cursor.fetchall()]
        
        cursor.execute(sql.SQL("SELECT * FROM {} LIMIT %s").format(sql.Identifier(table_name)), (limit,))
        rows = cursor.fetchall()
        
        print(f"\n📄 DATA IN '{table_name}' (first {limit} rows):")
        print("-" * 60)
        
        if rows:
            print(f"  Columns: {columns}")
            print()
            for row in rows:
                print(f"  {row}")
        else:
            print("  (empty table - no data)")
        
        print("-" * 60)
        return rows
    except Exception as e:
        print(f"  ❌ Error reading table: {e}")
        return []


def show_data_to_insert():
    """Show what data will be inserted from the file"""
    print("\n📦 DATA TO INSERT (from learnership_emails.py):")
    print("-" * 60)
    for i, data in enumerate(learnership_email_data, 1):
        print(f"  {i}. {data['company_name']} - {data['email']}")
    print("-" * 60)
    print(f"  Total records: {len(learnership_email_data)}")


def insert_data_no_duplicates(conn, table_name):
    """Insert data while preventing duplicates"""
    cursor = conn.cursor()
    
    inserted = 0
    skipped = 0
    
    print("\n🚀 INSERTING DATA (No Duplicates)...")
    print("-" * 50)
    
    for data in learnership_email_data:
        # Check if email already exists (case-insensitive)
        cursor.execute(
            sql.SQL("SELECT EXISTS(SELECT 1 FROM {} WHERE LOWER(email) = LOWER(%s))")
            .format(sql.Identifier(table_name)),
            (data["email"],)
        )
        exists = cursor.fetchone()[0]
        
        if exists:
            print(f"  ⏭️  Skipped (duplicate): {data['email']}")
            skipped += 1
        else:
            cursor.execute(
                sql.SQL("INSERT INTO {} (company_name, email) VALUES (%s, %s)")
                .format(sql.Identifier(table_name)),
                (data["company_name"], data["email"])
            )
            print(f"  ✅ Inserted: {data['company_name']} - {data['email']}")
            inserted += 1
    
    print("-" * 50)
    return inserted, skipped


def add_missing_column(conn):
    """Add missing company_email column to application table"""
    cursor = conn.cursor()
    
    print("\n🔧 ADD MISSING COLUMN TO APPLICATION TABLE")
    print("=" * 60)
    
    # First check if the column already exists
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'application' AND column_name = 'company_email';
    """)
    
    existing_column = cursor.fetchone()
    
    if existing_column:
        print("✅ Column 'company_email' already exists in 'application' table!")
        return False
    
    print("📋 Current 'application' table structure:")
    show_table_structure(conn, 'application')
    
    print("\n🎯 WILL ADD: company_email VARCHAR(255)")
    print("\n⚠️  This will:")
    print("   • Add 'company_email' column to all 2535+ existing records")
    print("   • Set initial value to NULL for existing records")
    print("   • This operation is SAFE and reversible")
    
    confirm = input("\nType 'ADD COLUMN' to proceed: ")
    
    if confirm != "ADD COLUMN":
        print("❌ Aborted. No changes made.")
        return False
    
    try:
        # Add the column
        cursor.execute("""
            ALTER TABLE application 
            ADD COLUMN company_email VARCHAR(255);
        """)
        
        print("\n✅ Column 'company_email' successfully added!")
        print("\n📋 Updated table structure:")
        show_table_structure(conn, 'application')
        
        return True
        
    except Exception as e:
        print(f"\n❌ Failed to add column: {e}")
        return False


def rename_column(conn):
    """Safely rename email to email_address in learnership_email table"""
    cursor = conn.cursor()
    
    print("\n🔧 RENAME COLUMN: email → email_address")
    print("=" * 60)
    
    # First check current structure
    print("📋 Current 'learnership_email' table structure:")
    show_table_structure(conn, 'learnership_email')
    
    # Check if email column exists and email_address doesn't
    cursor.execute("""
        SELECT 
            COUNT(CASE WHEN column_name = 'email' THEN 1 END) as has_email,
            COUNT(CASE WHEN column_name = 'email_address' THEN 1 END) as has_email_address
        FROM information_schema.columns 
        WHERE table_name = 'learnership_email';
    """)
    
    has_email, has_email_address = cursor.fetchone()
    
    if has_email_address > 0:
        print("✅ Column 'email_address' already exists!")
        return False
        
    if has_email == 0:
        print("❌ Column 'email' does not exist!")
        return False
    
    # Show sample data that will be preserved
    cursor.execute("SELECT id, company_name, email FROM learnership_email LIMIT 5;")
    sample_data = cursor.fetchall()
    
    print(f"\n📄 SAMPLE DATA TO BE PRESERVED:")
    print("-" * 50)
    for row in sample_data:
        print(f"  ID: {row[0]} | Company: {row[1]} | Email: {row[2]}")
    print("-" * 50)
    
    print("\n⚠️  This will:")
    print("   • Rename column 'email' to 'email_address'")
    print("   • Preserve ALL existing data")
    print("   • This operation is SAFE and reversible")
    
    confirm = input("\nType 'RENAME COLUMN' to proceed: ")
    
    if confirm != "RENAME COLUMN":
        print("❌ Aborted. No changes made.")
        return False
    
    try:
        # PostgreSQL rename column syntax
        cursor.execute("""
            ALTER TABLE learnership_email 
            RENAME COLUMN email TO email_address;
        """)
        
        print("\n✅ Column successfully renamed: email → email_address")
        print("\n📋 Updated table structure:")
        show_table_structure(conn, 'learnership_email')
        
        # Verify data is intact
        cursor.execute("SELECT COUNT(*) FROM learnership_email;")
        count = cursor.fetchone()[0]
        print(f"\n✅ Data verification: {count} rows preserved")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Failed to rename column: {e}")
        return False


def add_missing_columns_to_learnership_email(conn):
    """Add all missing columns to learnership_email table to match local schema"""
    cursor = conn.cursor()
    
    print("\n🔧 ADD MISSING COLUMNS TO LEARNERSHIP_EMAIL TABLE")
    print("=" * 60)
    
    # Define all the columns that should exist
    required_columns = [
        ("is_reachable", "BOOLEAN DEFAULT TRUE"),
        ("response_time", "FLOAT"),
        ("last_checked", "TIMESTAMP"),
        ("check_count", "INTEGER DEFAULT 0"),
        ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ("updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ("is_active", "BOOLEAN DEFAULT TRUE")
    ]
    
    # Check current structure
    print("📋 Current 'learnership_email' table structure:")
    show_table_structure(conn, 'learnership_email')
    
    # Check which columns are missing
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'learnership_email';
    """)
    existing_columns = [row[0] for row in cursor.fetchall()]
    
    missing_columns = [(col, definition) for col, definition in required_columns 
                      if col not in existing_columns]
    
    if not missing_columns:
        print("\n✅ All columns already exist!")
        return False
    
    print(f"\n🎯 WILL ADD {len(missing_columns)} MISSING COLUMNS:")
    for col, definition in missing_columns:
        print(f"   • {col} ({definition})")
    
    print("\n⚠️  This will:")
    print(f"   • Add {len(missing_columns)} new columns to all existing records")
    print("   • Set default values where specified")
    print("   • This operation is SAFE and reversible")
    
    confirm = input("\nType 'ADD COLUMNS' to proceed: ")
    
    if confirm != "ADD COLUMNS":
        print("❌ Aborted. No changes made.")
        return False
    
    try:
        added = 0
        for col, definition in missing_columns:
            cursor.execute(sql.SQL("""
                ALTER TABLE learnership_email 
                ADD COLUMN {} {};
            """).format(sql.Identifier(col), sql.SQL(definition)))
            print(f"  ✅ Added column: {col}")
            added += 1
        
        print(f"\n✅ Successfully added {added} columns!")
        print("\n📋 Updated table structure:")
        show_table_structure(conn, 'learnership_email')
        
        return True
        
    except Exception as e:
        print(f"\n❌ Failed to add columns: {e}")
        return False


def delete_empty_tables(conn, empty_tables):
    """Delete all empty tables with confirmation"""
    cursor = conn.cursor()
    
    if not empty_tables:
        print("\n✅ No empty tables to delete!")
        return 0
    
    print("\n" + "=" * 60)
    print("⚠️  WARNING: DELETE EMPTY TABLES")
    print("=" * 60)
    print("\n🗑️  The following empty tables will be PERMANENTLY DELETED:")
    print("-" * 60)
    for table in empty_tables:
        print(f"   • {table}")
    print("-" * 60)
    print(f"\n   Total tables to delete: {len(empty_tables)}")
    
    print("\n⚠️  THIS ACTION CANNOT BE UNDONE!")
    
    confirm1 = input("Type 'DELETE' to proceed: ")
    if confirm1 != "DELETE":
        print("❌ Aborted. No tables were deleted.")
        return 0
    
    confirm2 = input("Are you ABSOLUTELY sure? Type 'YES' to confirm: ")
    if confirm2 != "YES":
        print("❌ Aborted. No tables were deleted.")
        return 0
    
    deleted = 0
    failed = 0
    
    print("\n🗑️  DELETING TABLES...")
    print("-" * 50)
    
    for table in empty_tables:
        try:
            cursor.execute(sql.SQL("DROP TABLE IF EXISTS {} CASCADE").format(sql.Identifier(table)))
            print(f"  ✅ Deleted: {table}")
            deleted += 1
        except Exception as e:
            print(f"  ❌ Failed to delete '{table}': {e}")
            failed += 1
    
    print("-" * 50)
    print(f"\n📊 RESULT: Deleted: {deleted}, Failed: {failed}")
    
    return deleted


def delete_single_table(conn):
    """Delete a specific table"""
    cursor = conn.cursor()
    
    table_name = input("\nEnter the table name to delete: ").strip()
    
    if not table_name:
        print("❌ No table name provided.")
        return
    
    cursor.execute("""
        SELECT EXISTS(
            SELECT 1 FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = %s
        );
    """, (table_name,))
    
    exists = cursor.fetchone()[0]
    
    if not exists:
        print(f"❌ Table '{table_name}' does not exist!")
        return
    
    cursor.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table_name)))
    count = cursor.fetchone()[0]
    
    print(f"\n⚠️  TABLE: {table_name}")
    print(f"   Rows: {count}")
    
    if count > 0:
        print(f"\n🚨 WARNING: This table has {count} rows of data!")
    
    show_table_structure(conn, table_name)
    
    print("\n⚠️  THIS ACTION CANNOT BE UNDONE!")
    confirm = input(f"Type '{table_name}' to confirm deletion: ")
    
    if confirm != table_name:
        print("❌ Aborted. Table was not deleted.")
        return
    
    try:
        cursor.execute(sql.SQL("DROP TABLE IF EXISTS {} CASCADE").format(sql.Identifier(table_name)))
        print(f"\n✅ Table '{table_name}' has been deleted!")
    except Exception as e:
        print(f"\n❌ Failed to delete table: {e}")


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 60)
    print("🗄️  PRODUCTION DATABASE MANAGEMENT SCRIPT")
    print("=" * 60)
    
    conn = connect_db()
    if not conn:
        return
    
    try:
        tables, empty_tables, non_empty_tables = discover_tables_with_counts(conn)
        
        if not tables:
            print("\n⚠️ No tables found. Closing connection.")
            conn.close()
            return
        
        while True:
            print("\n🤔 WHAT WOULD YOU LIKE TO DO?")
            print("   1. View a table's structure")
            print("   2. View a table's data")
            print("   3. Insert learnership data (no duplicates)")
            print("   4. Refresh table list")
            print("   5. 🗑️  Delete ALL empty tables")
            print("   6. 🗑️  Delete a specific table")
            print("   7. 📦 View data to be inserted")
            print("   8. 🔧 Add company_email column to application")
            print("   9. 🔧 Rename email → email_address in learnership_email")
            print("   10. 🔧 Add missing columns to learnership_email")
            print("   11. Exit")
            
            choice = input("\nEnter choice (1-11): ")
            
            if choice == "1":
                table = input("Enter table name: ")
                show_table_structure(conn, table)
                
            elif choice == "2":
                table = input("Enter table name: ")
                show_table_structure(conn, table)
                show_existing_data(conn, table)
                
            elif choice == "3":
                table = input(f"Enter table name (default: {TABLE_NAME}): ") or TABLE_NAME
                
                columns = show_table_structure(conn, table)
                if not columns:
                    continue
                
                show_existing_data(conn, table)
                show_data_to_insert()
                
                print("\n⚠️  READY TO INSERT DATA INTO PRODUCTION")
                print(f"   Table: {table}")
                print(f"   Records to insert: {len(learnership_email_data)}")
                confirm = input("\nType 'YES' to proceed: ")
                
                if confirm != "YES":
                    print("❌ Aborted by user.")
                    continue
                
                inserted, skipped = insert_data_no_duplicates(conn, table)
                conn.commit()
                print(f"\n🎉 SUCCESS! Inserted: {inserted}, Skipped: {skipped}")
                show_existing_data(conn, table)
                
            elif choice == "4":
                tables, empty_tables, non_empty_tables = discover_tables_with_counts(conn)
                
            elif choice == "5":
                if not empty_tables:
                    print("\n✅ No empty tables to delete!")
                    continue
                
                deleted = delete_empty_tables(conn, empty_tables)
                
                if deleted > 0:
                    conn.commit()
                    print("\n✅ Changes committed to database.")
                    tables, empty_tables, non_empty_tables = discover_tables_with_counts(conn)
                    
            elif choice == "6":
                delete_single_table(conn)
                conn.commit()
                tables, empty_tables, non_empty_tables = discover_tables_with_counts(conn)
                
            elif choice == "7":
                show_data_to_insert()
                
            elif choice == "8":
                success = add_missing_column(conn)
                if success:
                    conn.commit()
                    print("✅ Changes committed to database.")
                
            elif choice == "9":
                success = rename_column(conn)
                if success:
                    conn.commit()
                    print("✅ Changes committed to database.")
                    
            elif choice == "10":
                success = add_missing_columns_to_learnership_email(conn)
                if success:
                    conn.commit()
                    print("✅ Changes committed to database.")
                
            elif choice == "11":
                print("\n👋 Goodbye!")
                break
            
            else:
                print("❌ Invalid choice. Please enter 1-11.")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ ERROR: {e}")
        print("🔄 Transaction rolled back. No changes made.")
    
    finally:
        conn.close()
        print("\n👋 Connection closed.")


if __name__ == "__main__":
    main()