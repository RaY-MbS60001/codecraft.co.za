import sqlite3
import os
import json
from datetime import datetime

# ============================================================
# CONFIGURATION
# ============================================================
DB_PATH = "instance/codecraft.db"
BACKUP_PATH = "instance/backup_codecraft.db"

# ============================================================
# DATABASE CONNECTION
# ============================================================

def connect_db():
    """Connect to local SQLite database"""
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found: {DB_PATH}")
        return None
    
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        print(f"✅ Connected to local database: {DB_PATH}")
        print(f"📊 Database size: {os.path.getsize(DB_PATH):,} bytes")
        return conn
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return None

def discover_tables_with_counts(conn):
    """List all tables with row counts"""
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = cursor.fetchall()
    
    print("\n📋 TABLES IN YOUR LOCAL DATABASE:")
    print("=" * 70)
    print(f"{'TABLE NAME':<30} {'ROWS':<10} {'STATUS':<20} {'LAST MODIFIED'}")
    print("-" * 70)
    
    empty_tables = []
    non_empty_tables = []
    
    for table in tables:
        table_name = table[0]
        try:
            cursor.execute(f"SELECT COUNT(*) FROM `{table_name}`")
            count = cursor.fetchone()[0]
            
            # Get last modification info (approximate)
            try:
                cursor.execute(f"SELECT MAX(rowid) FROM `{table_name}`")
                max_rowid = cursor.fetchone()[0] or 0
                last_mod = f"Row #{max_rowid}" if max_rowid > 0 else "No data"
            except:
                last_mod = "Unknown"
            
            if count == 0:
                status = "🔴 EMPTY"
                empty_tables.append(table_name)
            else:
                status = "🟢 Has data"
                non_empty_tables.append((table_name, count))
            
            print(f"  {table_name:<28} {count:<10} {status:<20} {last_mod}")
        except Exception as e:
            print(f"  {table_name:<28} {'?':<10} ⚠️ Error: {str(e)[:15]}...")
    
    print("-" * 70)
    
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
            print(f"   • {t} ({count:,} rows)")
    
    print("=" * 70)
    
    return [t[0] for t in tables], empty_tables, non_empty_tables

def show_table_structure(conn, table_name):
    """Show table schema and indexes"""
    cursor = conn.cursor()
    
    # Get table schema
    cursor.execute(f"PRAGMA table_info(`{table_name}`)")
    columns = cursor.fetchall()
    
    print(f"\n📊 STRUCTURE OF '{table_name}':")
    print("-" * 80)
    
    if columns:
        print(f"{'COLUMN':<25} {'TYPE':<15} {'NULL':<8} {'KEY':<10} {'DEFAULT'}")
        print("-" * 80)
        for col in columns:
            col_name = col[1]
            col_type = col[2]
            not_null = "NOT NULL" if col[3] else "NULL"
            primary_key = "PRIMARY" if col[5] else ""
            default_val = col[4] if col[4] is not None else ""
            
            print(f"  {col_name:<23} {col_type:<15} {not_null:<8} {primary_key:<10} {default_val}")
        
        # Show indexes
        cursor.execute(f"PRAGMA index_list(`{table_name}`)")
        indexes = cursor.fetchall()
        
        if indexes:
            print("\n🔗 INDEXES:")
            for idx in indexes:
                cursor.execute(f"PRAGMA index_info(`{idx[1]}`)")
                idx_cols = [col[2] for col in cursor.fetchall()]
                unique = "UNIQUE" if idx[2] else "INDEX"
                print(f"  • {idx[1]} ({unique}): {', '.join(idx_cols)}")
    else:
        print(f"  ❌ Table '{table_name}' not found!")
    
    print("-" * 80)
    return columns

def show_existing_data(conn, table_name, limit=10):
    """Show sample data from table"""
    cursor = conn.cursor()
    
    try:
        cursor.execute(f"SELECT * FROM `{table_name}` LIMIT {limit}")
        rows = cursor.fetchall()
        
        print(f"\n📄 SAMPLE DATA FROM '{table_name}' (first {limit} rows):")
        print("-" * 100)
        
        if rows:
            # Get column names
            column_names = [description[0] for description in cursor.description]
            
            # Show column headers
            header = " | ".join(f"{col[:12]:<12}" for col in column_names)
            print(f"  {header}")
            print("  " + "-" * len(header))
            
            # Show data rows
            for row in rows:
                row_data = []
                for item in row:
                    if item is None:
                        row_data.append("NULL")
                    elif isinstance(item, str) and len(item) > 12:
                        row_data.append(item[:9] + "...")
                    else:
                        row_data.append(str(item))
                
                row_str = " | ".join(f"{item:<12}" for item in row_data)
                print(f"  {row_str}")
        else:
            print("  (empty table - no data)")
        
        print("-" * 100)
        return rows
    except Exception as e:
        print(f"  ❌ Error reading table: {e}")
        return []

def inspect_applications_table(conn):
    """Detailed inspection of applications table"""
    cursor = conn.cursor()
    
    print("\n🔍 DETAILED APPLICATIONS ANALYSIS:")
    print("=" * 80)
    
    try:
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='application'")
        if not cursor.fetchone():
            print("❌ 'application' table not found!")
            return
        
        # Basic stats
        cursor.execute("SELECT COUNT(*) as total FROM application")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT user_id) as unique_users FROM application")
        unique_users = cursor.fetchone()[0]
        
        print(f"📊 BASIC STATS:")
        print(f"   Total applications: {total}")
        print(f"   Unique users: {unique_users}")
        
        # Gmail tracking analysis
        cursor.execute("SELECT COUNT(*) FROM application WHERE gmail_message_id IS NOT NULL")
        with_gmail = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM application WHERE sent_at IS NOT NULL")
        with_sent_date = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM application WHERE has_response = 1")
        with_responses = cursor.fetchone()[0]
        
        print(f"\n📧 GMAIL TRACKING:")
        print(f"   With Gmail message ID: {with_gmail}/{total}")
        print(f"   With sent date: {with_sent_date}/{total}")
        print(f"   With responses: {with_responses}/{total}")
        
        # Email status breakdown
        cursor.execute("SELECT email_status, COUNT(*) FROM application GROUP BY email_status ORDER BY COUNT(*) DESC")
        statuses = cursor.fetchall()
        
        print(f"\n📊 EMAIL STATUS BREAKDOWN:")
        for status, count in statuses:
            status_display = status or "NULL"
            print(f"   {status_display}: {count}")
        
        # User breakdown
        cursor.execute("""
            SELECT u.email, u.full_name, COUNT(a.id) as app_count,
                   COUNT(CASE WHEN a.gmail_message_id IS NOT NULL THEN 1 END) as with_gmail
            FROM user u
            LEFT JOIN application a ON u.id = a.user_id
            GROUP BY u.id, u.email, u.full_name
            HAVING app_count > 0
            ORDER BY app_count DESC
        """)
        users = cursor.fetchall()
        
        print(f"\n👥 APPLICATIONS BY USER:")
        print(f"{'EMAIL':<30} {'NAME':<20} {'APPS':<6} {'GMAIL'}")
        print("-" * 70)
        for user in users:
            email = user[0][:27] + "..." if len(user[0]) > 30 else user[0]
            name = (user[1] or "No name")[:17] + "..." if user[1] and len(user[1]) > 20 else (user[1] or "No name")
            apps = user[2]
            gmail_count = user[3]
            print(f"  {email:<28} {name:<18} {apps:<6} {gmail_count}")
        
        # Recent applications
        cursor.execute("""
            SELECT id, user_id, company_name, email_status, submitted_at, gmail_message_id
            FROM application 
            ORDER BY submitted_at DESC 
            LIMIT 5
        """)
        recent = cursor.fetchall()
        
        print(f"\n🕐 RECENT APPLICATIONS:")
        print(f"{'ID':<4} {'USER':<6} {'COMPANY':<20} {'STATUS':<12} {'DATE':<12} {'GMAIL'}")
        print("-" * 70)
        for app in recent:
            company = (app[2] or "Unknown")[:17] + "..." if app[2] and len(app[2]) > 20 else (app[2] or "Unknown")
            status = app[3] or "NULL"
            date = app[4][:10] if app[4] else "NULL"
            has_gmail = "✅" if app[5] else "❌"
            print(f"  {app[0]:<4} {app[1]:<6} {company:<18} {status:<12} {date:<12} {has_gmail}")
        
    except Exception as e:
        print(f"❌ Error analyzing applications: {e}")
    
    print("=" * 80)

def backup_database():
    """Create a backup of the database"""
    try:
        if os.path.exists(BACKUP_PATH):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_with_timestamp = f"instance/backup_codecraft_{timestamp}.db"
        else:
            backup_with_timestamp = BACKUP_PATH
        
        # Simple file copy for SQLite
        import shutil
        shutil.copy2(DB_PATH, backup_with_timestamp)
        
        print(f"✅ Database backed up to: {backup_with_timestamp}")
        return backup_with_timestamp
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        return None

def add_gmail_fields_to_application(conn):
    """Add Gmail tracking fields to application table if missing"""
    cursor = conn.cursor()
    
    print("\n🔧 CHECKING GMAIL FIELDS IN APPLICATION TABLE:")
    print("-" * 60)
    
    # Get current schema
    cursor.execute("PRAGMA table_info(application)")
    columns = {col[1]: col for col in cursor.fetchall()}
    
    # Fields to add
    gmail_fields = {
        'gmail_message_id': 'TEXT',
        'gmail_thread_id': 'TEXT',
        'email_status': 'TEXT DEFAULT "draft"',
        'delivered_at': 'DATETIME',
        'read_at': 'DATETIME',
        'response_received_at': 'DATETIME',
        'has_response': 'BOOLEAN DEFAULT 0',
        'response_thread_count': 'INTEGER DEFAULT 0',
        'sent_at': 'DATETIME'
    }
    
    fields_added = 0
    fields_exist = 0
    
    for field, definition in gmail_fields.items():
        if field in columns:
            print(f"  ✅ {field} - already exists")
            fields_exist += 1
        else:
            try:
                cursor.execute(f"ALTER TABLE application ADD COLUMN {field} {definition}")
                print(f"  ➕ {field} - added successfully")
                fields_added += 1
            except Exception as e:
                print(f"  ❌ {field} - failed to add: {e}")
    
    if fields_added > 0:
        conn.commit()
        print(f"\n✅ Added {fields_added} fields to application table")
        
        # Update existing records to have proper defaults
        cursor.execute("UPDATE application SET email_status = 'draft' WHERE email_status IS NULL")
        cursor.execute("UPDATE application SET has_response = 0 WHERE has_response IS NULL")
        cursor.execute("UPDATE application SET response_thread_count = 0 WHERE response_thread_count IS NULL")
        
        updated = cursor.rowcount
        conn.commit()
        print(f"✅ Updated {updated} existing records with default values")
    else:
        print(f"\n✅ All Gmail fields already exist ({fields_exist} fields)")
    
    print("-" * 60)

def search_table_data(conn):
    """Search for specific data in tables"""
    table_name = input("Enter table name to search: ").strip()
    if not table_name:
        return
    
    cursor = conn.cursor()
    
    # Check if table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    if not cursor.fetchone():
        print(f"❌ Table '{table_name}' not found!")
        return
    
    # Get table structure
    cursor.execute(f"PRAGMA table_info(`{table_name}`)")
    columns = [col[1] for col in cursor.fetchall()]
    
    print(f"\n🔍 Available columns in '{table_name}':")
    for i, col in enumerate(columns, 1):
        print(f"   {i}. {col}")
    
    column = input("Enter column name to search (or press Enter for all): ").strip()
    search_term = input("Enter search term: ").strip()
    
    if not search_term:
        return
    
    try:
        if column and column in columns:
            query = f"SELECT * FROM `{table_name}` WHERE `{column}` LIKE ? LIMIT 20"
            cursor.execute(query, (f"%{search_term}%",))
        else:
            # Search all text columns
            text_columns = []
            for col in columns:
                cursor.execute(f"SELECT `{col}` FROM `{table_name}` LIMIT 1")
                sample = cursor.fetchone()
                if sample and isinstance(sample[0], str):
                    text_columns.append(col)
            
            if text_columns:
                where_clause = " OR ".join([f"`{col}` LIKE ?" for col in text_columns])
                query = f"SELECT * FROM `{table_name}` WHERE {where_clause} LIMIT 20"
                cursor.execute(query, [f"%{search_term}%"] * len(text_columns))
            else:
                print("❌ No searchable text columns found!")
                return
        
        results = cursor.fetchall()
        
        if results:
            print(f"\n🔍 SEARCH RESULTS (found {len(results)} matches):")
            print("-" * 80)
            
            # Show column headers
            column_names = [description[0] for description in cursor.description]
            header = " | ".join(f"{col[:10]:<10}" for col in column_names)
            print(f"  {header}")
            print("  " + "-" * len(header))
            
            # Show results
            for row in results:
                row_data = []
                for item in row:
                    if item is None:
                        row_data.append("NULL")
                    elif isinstance(item, str) and len(item) > 10:
                        row_data.append(item[:7] + "...")
                    else:
                        row_data.append(str(item))
                
                row_str = " | ".join(f"{item:<10}" for item in row_data)
                print(f"  {row_str}")
        else:
            print(f"\n❌ No results found for '{search_term}'")
    
    except Exception as e:
        print(f"❌ Search error: {e}")

def export_table_to_json(conn):
    """Export table data to JSON file"""
    table_name = input("Enter table name to export: ").strip()
    if not table_name:
        return
    
    cursor = conn.cursor()
    
    try:
        cursor.execute(f"SELECT * FROM `{table_name}`")
        rows = cursor.fetchall()
        
        if not rows:
            print(f"❌ Table '{table_name}' is empty!")
            return
        
        # Convert to list of dictionaries
        column_names = [description[0] for description in cursor.description]
        data = []
        
        for row in rows:
            row_dict = {}
            for i, value in enumerate(row):
                # Handle datetime strings and other types
                if isinstance(value, str):
                    row_dict[column_names[i]] = value
                else:
                    row_dict[column_names[i]] = value
            data.append(row_dict)
        
        # Export to file
        filename = f"exports/{table_name}_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        # Create exports directory if it doesn't exist
        os.makedirs("exports", exist_ok=True)
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump({
                'table': table_name,
                'exported_at': datetime.now().isoformat(),
                'row_count': len(data),
                'data': data
            }, f, indent=2, default=str)
        
        print(f"✅ Exported {len(data)} rows to: {filename}")
    
    except Exception as e:
        print(f"❌ Export error: {e}")

# ============================================================
# MAIN MENU
# ============================================================

def main():
    print("=" * 70)
    print("🗄️  LOCAL SQLite DATABASE MANAGEMENT TOOL")
    print("=" * 70)
    print(f"Database: {DB_PATH}")
    
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
            print("   1.  📋 View table structure")
            print("   2.  📄 View table data")
            print("   3.  🔍 Detailed applications analysis")
            print("   4.  🔄 Refresh table list")
            print("   5.  🔧 Add Gmail fields to applications")
            print("   6.  🔍 Search table data")
            print("   7.  📤 Export table to JSON")
            print("   8.  💾 Backup database")
            print("   9.  🗑️  Drop empty tables")
            print("   10. 🗑️  Drop specific table")
            print("   11. 📊 Database statistics")
            print("   12. 🚪 Exit")
            
            choice = input("\nEnter choice (1-12): ").strip()
            
            if choice == "1":
                table = input("Enter table name: ").strip()
                if table:
                    show_table_structure(conn, table)
                
            elif choice == "2":
                table = input("Enter table name: ").strip()
                if table:
                    limit = input("Number of rows to show (default 10): ").strip()
                    limit = int(limit) if limit.isdigit() else 10
                    show_table_structure(conn, table)
                    show_existing_data(conn, table, limit)
                
            elif choice == "3":
                inspect_applications_table(conn)
                
            elif choice == "4":
                tables, empty_tables, non_empty_tables = discover_tables_with_counts(conn)
                
            elif choice == "5":
                add_gmail_fields_to_application(conn)
                
            elif choice == "6":
                search_table_data(conn)
                
            elif choice == "7":
                export_table_to_json(conn)
                
            elif choice == "8":
                backup_database()
                
            elif choice == "9":
                if not empty_tables:
                    print("\n✅ No empty tables to delete!")
                    continue
                
                print(f"\n⚠️  Empty tables to delete: {', '.join(empty_tables)}")
                confirm = input("Type 'YES' to delete all empty tables: ")
                
                if confirm == "YES":
                    cursor = conn.cursor()
                    deleted = 0
                    for table in empty_tables:
                        try:
                            cursor.execute(f"DROP TABLE IF EXISTS `{table}`")
                            print(f"✅ Deleted: {table}")
                            deleted += 1
                        except Exception as e:
                            print(f"❌ Failed to delete {table}: {e}")
                    
                    conn.commit()
                    print(f"\n✅ Deleted {deleted} empty tables")
                    tables, empty_tables, non_empty_tables = discover_tables_with_counts(conn)
                else:
                    print("❌ Cancelled")
                
            elif choice == "10":
                table = input("Enter table name to delete: ").strip()
                if table:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM `{}`".format(table))
                    count = cursor.fetchone()[0]
                    
                    print(f"\n⚠️  Table '{table}' has {count} rows")
                    confirm = input(f"Type '{table}' to confirm deletion: ")
                    
                    if confirm == table:
                        try:
                            cursor.execute(f"DROP TABLE IF EXISTS `{table}`")
                            conn.commit()
                            print(f"✅ Table '{table}' deleted!")
                            tables, empty_tables, non_empty_tables = discover_tables_with_counts(conn)
                        except Exception as e:
                            print(f"❌ Failed to delete: {e}")
                    else:
                        print("❌ Cancelled")
                
            elif choice == "11":
                # Database statistics
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
                table_count = cursor.fetchone()[0]
                
                print(f"\n📊 DATABASE STATISTICS:")
                print(f"   Database file: {DB_PATH}")
                print(f"   File size: {os.path.getsize(DB_PATH):,} bytes")
                print(f"   Tables: {table_count}")
                print(f"   Empty tables: {len(empty_tables)}")
                print(f"   Tables with data: {len(non_empty_tables)}")
                
                total_rows = sum(count for _, count in non_empty_tables)
                print(f"   Total rows: {total_rows:,}")
                
            elif choice == "12":
                print("\n👋 Goodbye!")
                break
            
            else:
                print("❌ Invalid choice. Please enter 1-12.")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        conn.close()
        print("\n👋 Connection closed.")

if __name__ == "__main__":
    main()