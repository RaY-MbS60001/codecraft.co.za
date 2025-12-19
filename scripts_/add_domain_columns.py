"""
Add domain checking columns to production database
Run this once to add the missing columns
"""

import os
import psycopg2
from urllib.parse import urlparse

# Your production database URL
DATABASE_URL = "postgresql://codecraftco_db_user:84u1KfAY4jHElF1ISEVw4YNbtZM51691@dpg-d1lknv6r433s73drf130-a.oregon-postgres.render.com:5432/codecraftco_db"

def add_domain_checking_columns():
    """Add domain checking columns to production database"""
    try:
        # Parse the database URL
        result = urlparse(DATABASE_URL)
        
        # Connect to database
        conn = psycopg2.connect(
            database=result.path[1:],
            user=result.username,
            password=result.password,
            host=result.hostname,
            port=result.port
        )
        
        cur = conn.cursor()
        
        print("🔗 Connected to production database")
        
        # Add the missing columns
        columns_to_add = [
            "ALTER TABLE learnership_email ADD COLUMN IF NOT EXISTS failure_count INTEGER DEFAULT 0",
            "ALTER TABLE learnership_email ADD COLUMN IF NOT EXISTS mx_server VARCHAR(255)",
            "ALTER TABLE learnership_email ADD COLUMN IF NOT EXISTS check_status VARCHAR(50) DEFAULT 'pending'",
            "ALTER TABLE learnership_email ADD COLUMN IF NOT EXISTS domain_valid BOOLEAN",
            "ALTER TABLE learnership_email ADD COLUMN IF NOT EXISTS smtp_valid BOOLEAN"
        ]
        
        for sql in columns_to_add:
            print(f"📝 Executing: {sql}")
            cur.execute(sql)
        
        # Commit changes
        conn.commit()
        print("✅ All domain checking columns added successfully!")
        
        # Verify columns exist
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'learnership_email'
            ORDER BY column_name
        """)
        
        columns = [row[0] for row in cur.fetchall()]
        print(f"📊 Current columns: {columns}")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    add_domain_checking_columns()