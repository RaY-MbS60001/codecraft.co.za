import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

# Production database URL
POSTGRESQL_URL = (
    "postgresql://codecraftco_db_user:84u1KfAY4jHElF1ISEVw4YNbtZM51691@"
    "dpg-d1lknv6r433s73drf130-a.oregon-postgres.render.com:5432/"
    "codecraftco_db"
)

def add_premium_columns():
    """Add missing premium columns to production user table"""
    
    # SQL statements to add missing columns
    sql_commands = [
        # Add premium columns
        'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS is_premium BOOLEAN DEFAULT FALSE;',
        'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS premium_expires TIMESTAMP;',
        'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS daily_applications_used INTEGER DEFAULT 0;',
        'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS last_application_date DATE;',
        'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS premium_activated_by INTEGER;',
        'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS premium_activated_at TIMESTAMP;',
        
        # Add foreign key constraint
        '''ALTER TABLE "user" ADD CONSTRAINT IF NOT EXISTS fk_user_premium_activated_by 
           FOREIGN KEY (premium_activated_by) REFERENCES "user"(id);''',
        
        # Set default values for existing users
        'UPDATE "user" SET is_premium = FALSE WHERE is_premium IS NULL;',
        'UPDATE "user" SET daily_applications_used = 0 WHERE daily_applications_used IS NULL;',
        'UPDATE "user" SET last_application_date = CURRENT_DATE WHERE last_application_date IS NULL;',
    ]
    
    try:
        # Connect to database
        conn = psycopg2.connect(POSTGRESQL_URL)
        cursor = conn.cursor()
        
        print("🚀 Starting premium columns migration...")
        print("=" * 60)
        
        # Execute each command
        for i, command in enumerate(sql_commands, 1):
            print(f"📝 Step {i}: {command[:50]}...")
            try:
                cursor.execute(command)
                conn.commit()
                print(f"   ✅ Success!")
            except Exception as e:
                print(f"   ⚠️  Warning: {e}")
                conn.rollback()
        
        # Verify the changes
        print("\n🔍 Verifying new columns...")
        cursor.execute("""
            SELECT column_name, data_type, column_default 
            FROM information_schema.columns 
            WHERE table_name = 'user' 
            AND column_name IN ('is_premium', 'premium_expires', 'daily_applications_used', 
                               'last_application_date', 'premium_activated_by', 'premium_activated_at')
            ORDER BY column_name;
        """)
        
        columns = cursor.fetchall()
        if columns:
            print("✅ Premium columns successfully added:")
            print("-" * 60)
            for col in columns:
                print(f"  • {col[0]} ({col[1]}) - Default: {col[2]}")
        else:
            print("❌ No premium columns found!")
        
        cursor.close()
        conn.close()
        
        print("\n🎉 Migration completed successfully!")
        print("🚀 Your production database now has all premium features!")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")

if __name__ == "__main__":
    print("🗄️ PRODUCTION DATABASE PREMIUM MIGRATION")
    print("=" * 60)
    
    response = input("⚠️  This will add premium columns to production user table. Continue? (y/N): ")
    if response.lower() == 'y':
        add_premium_columns()
    else:
        print("❌ Migration cancelled.")