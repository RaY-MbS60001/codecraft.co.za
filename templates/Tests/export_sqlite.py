import sqlite3
import pandas as pd
import os

# Check both possible locations
db_paths = ['database.db', 'instance/database.db']
db_path = None

for path in db_paths:
    if os.path.exists(path):
        db_path = path
        break

if db_path:
    print(f"✅ Found database at: {db_path}")
    conn = sqlite3.connect(db_path)
    
    # Get all table names
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    print("Found tables:")
    for table in tables:
        table_name = table[0]
        print(f"- {table_name}")
        
        # Export each table to CSV
        try:
            df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
            df.to_csv(f"{table_name}.csv", index=False)
            print(f"  ✅ Exported {len(df)} rows to {table_name}.csv")
        except Exception as e:
            print(f"  ❌ Error exporting {table_name}: {e}")
    
    conn.close()
else:
    print("❌ Database file not found!")
    print("Checked locations:")
    for path in db_paths:
        print(f"  - {path}")