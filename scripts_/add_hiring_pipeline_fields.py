"""
Script to add hiring pipeline fields to Application table
"""
import os
import sys

# Add the parent directory to sys.path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from sqlalchemy import text

def add_hiring_pipeline_fields():
    """Add hiring pipeline fields to Application table"""
    with app.app_context():
        try:
            # Add hiring pipeline fields
            pipeline_fields = [
                "ALTER TABLE application ADD COLUMN application_stage VARCHAR(50) DEFAULT 'applied';",
                "ALTER TABLE application ADD COLUMN interview_date DATETIME;",
                "ALTER TABLE application ADD COLUMN interview_time VARCHAR(20);",
                "ALTER TABLE application ADD COLUMN interview_type VARCHAR(50);",  # virtual, in-person, phone
                "ALTER TABLE application ADD COLUMN interview_location TEXT;",
                "ALTER TABLE application ADD COLUMN interview_notes TEXT;",
                "ALTER TABLE application ADD COLUMN corporate_notes TEXT;",
                "ALTER TABLE application ADD COLUMN rejection_reason TEXT;",
                "ALTER TABLE application ADD COLUMN hire_date DATETIME;",
                "ALTER TABLE application ADD COLUMN last_corporate_action DATETIME;",
                "ALTER TABLE application ADD COLUMN corporate_user_id INTEGER;",  # Who handled this application
                "ALTER TABLE application ADD COLUMN interview_reminder_sent BOOLEAN DEFAULT FALSE;",
                "ALTER TABLE application ADD COLUMN applicant_notified BOOLEAN DEFAULT FALSE;"
            ]
            
            for field_sql in pipeline_fields:
                try:
                    db.session.execute(text(field_sql))
                    print(f"✅ Added field: {field_sql.split('ADD COLUMN')[1].split()[0]}")
                except Exception as e:
                    if "already exists" in str(e) or "duplicate column" in str(e).lower():
                        print(f"⚠️  Field already exists: {field_sql.split('ADD COLUMN')[1].split()[0]}")
                    else:
                        print(f"❌ Error adding field: {e}")
            
            db.session.commit()
            print("✅ Hiring pipeline fields migration completed successfully!")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Migration failed: {e}")
            return False
        
        return True

def create_calendar_events_table():
    """Create calendar events table for interview scheduling"""
    with app.app_context():
        try:
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS calendar_event (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                application_id INTEGER NOT NULL,
                corporate_user_id INTEGER NOT NULL,
                applicant_user_id INTEGER NOT NULL,
                event_type VARCHAR(50) DEFAULT 'interview',
                title VARCHAR(200) NOT NULL,
                description TEXT,
                start_datetime DATETIME NOT NULL,
                end_datetime DATETIME NOT NULL,
                location VARCHAR(200),
                meeting_link VARCHAR(500),
                google_event_id VARCHAR(200),
                status VARCHAR(50) DEFAULT 'scheduled',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                reminder_sent BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (application_id) REFERENCES application (id),
                FOREIGN KEY (corporate_user_id) REFERENCES user (id),
                FOREIGN KEY (applicant_user_id) REFERENCES user (id)
            );
            """
            
            db.session.execute(text(create_table_sql))
            db.session.commit()
            print("✅ CalendarEvent table created successfully!")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Calendar table creation failed: {e}")
            return False
        
        return True

def create_application_messages_table():
    """Create table for corporate-applicant messaging"""
    with app.app_context():
        try:
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS application_message (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                application_id INTEGER NOT NULL,
                sender_id INTEGER NOT NULL,
                sender_type VARCHAR(20) NOT NULL,
                subject VARCHAR(200),
                message TEXT NOT NULL,
                message_type VARCHAR(50) DEFAULT 'general',
                gmail_message_id VARCHAR(200),
                sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                read_at DATETIME,
                is_read BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (application_id) REFERENCES application (id),
                FOREIGN KEY (sender_id) REFERENCES user (id)
            );
            """
            
            db.session.execute(text(create_table_sql))
            db.session.commit()
            print("✅ ApplicationMessage table created successfully!")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Message table creation failed: {e}")
            return False
        
        return True

if __name__ == "__main__":
    print("🚀 Starting hiring pipeline migration...")
    print("=" * 50)
    
    # Add hiring pipeline fields
    if add_hiring_pipeline_fields():
        # Create calendar events table
        if create_calendar_events_table():
            # Create messaging table
            if create_application_messages_table():
                print("=" * 50)
                print("✅ All hiring pipeline migrations completed successfully!")
                print("🎉 Enhanced email workflow system is ready!")
            else:
                print("❌ Message table creation failed")
        else:
            print("❌ Calendar table creation failed")
    else:
        print("❌ Hiring pipeline fields migration failed")