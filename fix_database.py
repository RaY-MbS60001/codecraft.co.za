import sqlite3
import os
from app import app

def fix_database():
    with app.app_context():
        # Get the database path
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        print(f"Database path: {db_path}")
        
        if not os.path.exists(db_path):
            print("Database file not found!")
            return
        
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        try:
            # Check current conversation table structure
            cursor.execute("PRAGMA table_info(conversation)")
            columns = cursor.fetchall()
            print("Current conversation table columns:")
            for col in columns:
                print(f"  - {col[1]} ({col[2]})")
            
            # Check if last_read_at column exists
            column_names = [col[1] for col in columns]
            
            if 'last_read_at' not in column_names:
                print("\n❌ Missing last_read_at column. Adding it...")
                cursor.execute("ALTER TABLE conversation ADD COLUMN last_read_at DATETIME")
                print("✅ Added last_read_at column to conversation table")
            else:
                print("\n✅ last_read_at column already exists")
            
            # Check message table for is_read column
            cursor.execute("PRAGMA table_info(conversation_message)")
            msg_columns = cursor.fetchall()
            msg_column_names = [col[1] for col in msg_columns]
            
            if 'is_read' not in msg_column_names:
                print("\n❌ Missing is_read column in conversation_message. Adding it...")
                cursor.execute("ALTER TABLE conversation_message ADD COLUMN is_read BOOLEAN DEFAULT 0")
                print("✅ Added is_read column to conversation_message table")
            else:
                print("\n✅ is_read column already exists in conversation_message")
            
            conn.commit()
            print("\n🎉 Database structure updated successfully!")
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            conn.rollback()
        finally:
            conn.close()

if __name__ == "__main__":
    fix_database()