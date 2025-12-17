import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

POSTGRESQL_URL = (
    "postgresql://codecraftco_db_user:84u1KfAY4jHElF1ISEVw4YNbtZM51691@"
    "dpg-d1lknv6r433s73drf130-a.oregon-postgres.render.com:5432/"
    "codecraftco_db"
)

def add_foreign_key():
    try:
        conn = psycopg2.connect(POSTGRESQL_URL)
        cursor = conn.cursor()
        
        print("🔧 Adding foreign key constraint...")
        
        # Correct PostgreSQL syntax (no IF NOT EXISTS for constraints)
        sql = '''
        DO $$ 
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints 
                WHERE constraint_name = 'fk_user_premium_activated_by'
            ) THEN
                ALTER TABLE "user" ADD CONSTRAINT fk_user_premium_activated_by 
                FOREIGN KEY (premium_activated_by) REFERENCES "user"(id);
            END IF;
        END $$;
        '''
        
        cursor.execute(sql)
        conn.commit()
        
        print("✅ Foreign key constraint added successfully!")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    add_foreign_key()