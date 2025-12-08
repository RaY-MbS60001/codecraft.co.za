import psycopg2
from datetime import datetime

DB_CONFIG = {
    "host": "dpg-d1lknv6r433s73drf130-a.oregon-postgres.render.com",
    "port": "5432",
    "database": "codecraftco_db",
    "user": "codecraftco_db_user",
    "password": "84u1KfAY4jHElF1ISEVw4YNbtZM51691",
    "sslmode": "require"
}    
 
conn = psycopg2.connect(**DB_CONFIG)   
cursor = conn.cursor()

print("=" * 60)
print("🔧 FIXING NULL created_at VALUES")
print("=" * 60)
   
# Check how many have NULL created_at
cursor.execute("SELECT COUNT(*) FROM learnership_email WHERE created_at IS NULL")
null_count = cursor.fetchone()[0]
print(f"\n📊 Records with NULL created_at: {null_count}")

if null_count > 0:
    # Fix them
    cursor.execute("""
        UPDATE learnership_email 
        SET created_at = NOW() 
        WHERE created_at IS NULL
    """)
    updated = cursor.rowcount
    conn.commit()
    print(f"✅ Updated {updated} rows with current timestamp")
else:
    print("✅ No NULL values to fix!")

# Verify
cursor.execute("SELECT COUNT(*) FROM learnership_email WHERE created_at IS NULL")
remaining = cursor.fetchone()[0]
print(f"\n📊 Remaining NULL created_at: {remaining}")

conn.close()
print("\n👋 Done!")