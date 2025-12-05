from app import app, db
from models import Application
from sqlalchemy import text
import sqlite3
import os

def add_gmail_tracking_fields():
    """Add Gmail tracking fields to existing Application table"""
    with app.app_context():
        try:
            # For SQLite, we'll use direct connection
            db_path = None
            
            # Get the SQLite database path
            db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
            if db_uri.startswith('sqlite:///'):
                db_path = db_uri.replace('sqlite:///', '')
                if not os.path.isabs(db_path):
                    db_path = os.path.join(app.instance_path, os.path.basename(db_path))
            
            print(f"Database path: {db_path}")
            
            # Connect directly to SQLite
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Check existing columns
            cursor.execute("PRAGMA table_info(application)")
            existing_columns = [row[1] for row in cursor.fetchall()]
            print(f"Existing columns: {existing_columns}")
            
            # Define new fields to add
            fields_to_add = [
                ('sent_at', 'DATETIME'),
                ('gmail_message_id', 'VARCHAR(255)'),
                ('gmail_thread_id', 'VARCHAR(255)'),
                ('email_status', 'VARCHAR(50) DEFAULT "draft"'),
                ('delivered_at', 'DATETIME'),
                ('read_at', 'DATETIME'),
                ('response_received_at', 'DATETIME'),
                ('has_response', 'INTEGER DEFAULT 0'),
                ('response_thread_count', 'INTEGER DEFAULT 0')
            ]
            
            # Add missing fields
            for field_name, field_type in fields_to_add:
                if field_name not in existing_columns:
                    try:
                        query = f"ALTER TABLE application ADD COLUMN {field_name} {field_type}"
                        cursor.execute(query)
                        print(f"✓ Added field: {field_name}")
                    except Exception as e:
                        print(f"✗ Error adding {field_name}: {e}")
                else:
                    print(f"✓ Field already exists: {field_name}")
            
            # Set default values for existing records
            try:
                cursor.execute("UPDATE application SET email_status = 'draft' WHERE email_status IS NULL OR email_status = ''")
                cursor.execute("UPDATE application SET has_response = 0 WHERE has_response IS NULL")
                cursor.execute("UPDATE application SET response_thread_count = 0 WHERE response_thread_count IS NULL")
                print("✓ Set default values for existing records")
            except Exception as e:
                print(f"Warning: Could not set defaults: {e}")
            
            # Commit changes and close
            conn.commit()
            conn.close()
            
            print("✅ Gmail tracking fields added successfully!")
            
            # Verify with SQLAlchemy
            with db.engine.connect() as connection:
                result = connection.execute(text("PRAGMA table_info(application)"))
                columns = [row[1] for row in result.fetchall()]
                print(f"Final columns: {columns}")
                
        except Exception as e:
            print(f"✗ Error adding Gmail tracking fields: {e}")
            raise

if __name__ == '__main__':
    add_gmail_tracking_fields()