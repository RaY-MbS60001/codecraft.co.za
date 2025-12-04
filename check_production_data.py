import psycopg2

conn = psycopg2.connect('postgresql://codecraftco_db_user:84u1KfAY4jHElF1ISEVw4YNbtZM51691@dpg-d1lknv6r433s73drf130-a.oregon-postgres.render.com/codecraftco_db')
cur = conn.cursor()

print("=== CHECKING PRODUCTION DATA ===")

# Check all tables and their counts
tables = ['user', 'users', 'application', 'applications', 'learnership', 'learnerships']
for table in tables:
    try:
        cur.execute(f'SELECT COUNT(*) FROM "{table}"')
        count = cur.fetchone()[0]
        if count > 0:
            print(f' {table}: {count} records')
    except:
        print(f' {table}: table does not exist')

print("\n=== USER TABLE DETAILS ===")
try:
    cur.execute('SELECT id, email, full_name, role FROM "user" LIMIT 10')
    users = cur.fetchall()
    print(f"Users found: {len(users)}")
    for user in users:
        print(f"  - ID:{user[0]}, Email:{user[1]}, Name:{user[2]}, Role:{user[3]}")
except Exception as e:
    print(f"Error checking user table: {e}")

print("\n=== APPLICATIONS TABLE ===")
try:
    cur.execute('SELECT COUNT(*) FROM application')
    count = cur.fetchone()[0]
    print(f"Applications in 'application' table: {count}")
except Exception as e:
    print(f"Error checking application table: {e}")

try:
    cur.execute('SELECT COUNT(*) FROM applications')
    count = cur.fetchone()[0] 
    print(f"Applications in 'applications' table: {count}")
except Exception as e:
    print(f"Error checking applications table: {e}")

conn.close()
