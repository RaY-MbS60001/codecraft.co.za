import sqlite3
import os
from pathlib import Path

def fix_database():
    """Directly modify the SQLite database"""
    
    # Find the database file
    db_path = None
    possible_paths = [
        'instance/app.db',
        'app.db',
        'database.db',
        'codecraftco.db'
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            db_path = path
            break
    
    if not db_path:
        print("Database file not found. Looking for .db files...")
        for file in Path('.').glob('**/*.db'):
            print(f"Found: {file}")
            db_path = str(file)
            break
    
    if not db_path:
        print("No database file found!")
        return
    
    print(f"Using database: {db_path}")
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get current table structure
        cursor.execute("PRAGMA table_info(user)")
        columns = [col[1] for col in cursor.fetchall()]
        print(f"Current columns: {columns}")
        
        # Add missing columns
        session_columns = [
            ('session_token', 'VARCHAR(255)'),
            ('session_expires', 'DATETIME'),
            ('session_ip', 'VARCHAR(45)'),
            ('session_user_agent', 'VARCHAR(500)')
        ]
        
        for col_name, col_type in session_columns:
            if col_name not in columns:
                try:
                    cursor.execute(f"ALTER TABLE user ADD COLUMN {col_name} {col_type}")
                    print(f"✓ Added {col_name} column")
                except Exception as e:
                    print(f"✗ Error adding {col_name}: {e}")
            else:
                print(f"✓ {col_name} column already exists")
        
        conn.commit()
        conn.close()
        
        print("\nDatabase update completed!")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fix_database()