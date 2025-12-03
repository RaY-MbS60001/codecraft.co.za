import psycopg2

try:
    print("Connecting to production database...")
    conn = psycopg2.connect('postgresql://codecraftco_db_user:84u1KfAY4jHElF1ISEVw4YNbtZM51691@dpg-d1lknv6r433s73drf130-a.oregon-postgres.render.com/codecraftco_db')
    cur = conn.cursor()
    
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
    tables = [t[0] for t in cur.fetchall()]
    print(f'Production tables: {tables}')
    
    if 'user' in tables:
        cur.execute('SELECT COUNT(*) FROM "user"')
        users = cur.fetchone()[0]
        print(f'Users in production: {users}')
    
    if 'application' in tables:
        cur.execute('SELECT COUNT(*) FROM application')
        apps = cur.fetchone()[0]
        print(f'Applications in production: {apps}')
        
    if 'learnership' in tables:
        cur.execute('SELECT COUNT(*) FROM learnership')
        learnerships = cur.fetchone()[0]
        print(f'Learnerships in production: {learnerships}')
    
    conn.close()
    print(" Success!")
    
except Exception as e:
    print(f" Error: {e}")
