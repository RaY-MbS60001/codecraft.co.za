import psycopg2

conn = psycopg2.connect('postgresql://codecraftco_db_user:84u1KfAY4jHElF1ISEVw4YNbtZM51691@dpg-d1lknv6r433s73drf130-a.oregon-postgres.render.com/codecraftco_db')
cur = conn.cursor()

print("=== APPLICATION TABLE SCHEMA ===")
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'application' ORDER BY ordinal_position")
columns = cur.fetchall()

print("Columns that ACTUALLY exist in production:")
for col in columns:
    print(f"  - {col[0]}: {col[1]}")

print(f"\nTotal columns: {len(columns)}")
conn.close()
