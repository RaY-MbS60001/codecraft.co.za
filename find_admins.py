import psycopg2

conn = psycopg2.connect('postgresql://codecraftco_db_user:84u1KfAY4jHElF1ISEVw4YNbtZM51691@dpg-d1lknv6r433s73drf130-a.oregon-postgres.render.com/codecraftco_db')
cur = conn.cursor()

# Find admin users by role
cur.execute('SELECT id, email, username, role FROM "user" WHERE role = %s LIMIT 10', ('admin',))
admins = cur.fetchall()

print(f"Admin users (role='admin'):")
for admin in admins:
    print(f"  - ID: {admin[0]}, Email: {admin[1]}, Username: {admin[2]}, Role: {admin[3]}")

# Also check what roles exist
cur.execute('SELECT DISTINCT role FROM "user" WHERE role IS NOT NULL')
roles = cur.fetchall()
print(f"\nAll roles in database: {[r[0] for r in roles]}")

# Count users by role
cur.execute('SELECT role, COUNT(*) FROM "user" GROUP BY role')
role_counts = cur.fetchall()
print("\nUser counts by role:")
for role, count in role_counts:
    print(f"  - {role}: {count} users")

conn.close()
