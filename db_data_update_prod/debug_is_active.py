import psycopg2

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
print("🔍 DEBUGGING LEARNERSHIP_EMAIL TABLE")
print("=" * 60)

# Total count
cursor.execute("SELECT COUNT(*) FROM learnership_email")
total = cursor.fetchone()[0]
print(f"\n📊 Total rows: {total}")

# Count by is_active
print("\n📊 Breakdown by is_active:")
cursor.execute("""
    SELECT 
        CASE 
            WHEN is_active = TRUE THEN 'TRUE'
            WHEN is_active = FALSE THEN 'FALSE'
            ELSE 'NULL'
        END as status,
        COUNT(*) 
    FROM learnership_email 
    GROUP BY is_active
    ORDER BY is_active
""")
for row in cursor.fetchall():
    print(f"   is_active = {row[0]}: {row[1]} rows")

# Sample data
print("\n📄 Sample rows (first 5):")
cursor.execute("SELECT id, company_name, email, is_active FROM learnership_email LIMIT 5")
for row in cursor.fetchall():
    print(f"   {row}")

print("\n" + "=" * 60)

# The fix
print("\n🔧 TO FIX: Set all to is_active=TRUE?")
fix = input("Type 'FIX' to update all rows to is_active=TRUE: ")

if fix == "FIX":
    cursor.execute("""
        UPDATE learnership_email 
        SET is_active = TRUE 
        WHERE is_active IS NULL OR is_active = FALSE
    """)
    updated = cursor.rowcount
    conn.commit()  
    print(f"\n✅ Updated {updated} rows to is_active=TRUE")
    
    # Verify
    cursor.execute("SELECT COUNT(*) FROM learnership_email WHERE is_active = TRUE")
    print(f"✅ Total active now: {cursor.fetchone()[0]}")
else:
    print("❌ No changes made.")

conn.close()
print("\n👋 Done!")      