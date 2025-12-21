"""
Script to add corporate fields to existing User table
Run this to update your database schema
"""
import os
import sys

# Add the parent directory to sys.path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import User
from sqlalchemy import text

def add_corporate_fields():
    """Add corporate fields to the User table"""
    with app.app_context():
        try:
            # Add corporate fields to User table
            corporate_fields = [
                "ALTER TABLE user ADD COLUMN company_name VARCHAR(200);",
                "ALTER TABLE user ADD COLUMN company_email VARCHAR(120);",
                "ALTER TABLE user ADD COLUMN contact_person VARCHAR(100);",
                "ALTER TABLE user ADD COLUMN company_phone VARCHAR(20);",
                "ALTER TABLE user ADD COLUMN company_website VARCHAR(200);",
                "ALTER TABLE user ADD COLUMN company_address TEXT;",
                "ALTER TABLE user ADD COLUMN is_verified BOOLEAN DEFAULT FALSE;"
            ]
            
            for field_sql in corporate_fields:
                try:
                    db.session.execute(text(field_sql))
                    print(f"✅ Added field: {field_sql.split('ADD COLUMN')[1].split()[0]}")
                except Exception as e:
                    if "already exists" in str(e) or "duplicate column" in str(e).lower():
                        print(f"⚠️  Field already exists: {field_sql.split('ADD COLUMN')[1].split()[0]}")
                    else:
                        print(f"❌ Error adding field: {e}")
            
            db.session.commit()
            print("✅ Corporate fields migration completed successfully!")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Migration failed: {e}")
            return False
        
        return True

def create_learnership_opportunity_table():
    """Create the LearnearshipOpportunity table"""
    with app.app_context():
        try:
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS learnership_opportunity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL,
                title VARCHAR(200) NOT NULL,
                description TEXT NOT NULL,
                requirements TEXT,
                benefits TEXT,
                location VARCHAR(100),
                duration VARCHAR(50),
                stipend VARCHAR(50),
                application_email VARCHAR(120) NOT NULL,
                application_deadline DATETIME,
                max_applicants INTEGER,
                is_active BOOLEAN DEFAULT TRUE,
                is_featured BOOLEAN DEFAULT FALSE,
                expire_date DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_recurring BOOLEAN DEFAULT FALSE,
                recurring_frequency VARCHAR(20),
                next_post_date DATETIME,
                views_count INTEGER DEFAULT 0,
                applications_count INTEGER DEFAULT 0,
                FOREIGN KEY (company_id) REFERENCES user (id)
            );
            """
            
            db.session.execute(text(create_table_sql))
            db.session.commit()
            print("✅ LearnearshipOpportunity table created successfully!")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Table creation failed: {e}")
            return False
        
        return True

if __name__ == "__main__":
    print("🚀 Starting corporate system migration...")
    print("=" * 50)
    
    # Add corporate fields to User table
    if add_corporate_fields():
        # Create LearnearshipOpportunity table
        if create_learnership_opportunity_table():
            print("=" * 50)
            print("✅ All migrations completed successfully!")
            print("🎉 Corporate system is ready to use!")
        else:
            print("❌ LearnearshipOpportunity table creation failed")
    else:
        print("❌ Corporate fields migration failed")