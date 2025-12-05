import sqlite3
import os

db_path = 'instance/codecraft.db'
if os.path.exists(db_path):
    print(f'Database found: {db_path}')
    print(f'Size: {os.path.getsize(db_path)} bytes')
    
    conn = sqlite3.connect(db_path)
    
    # Check tables
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    print(f'Tables: {[t[0] for t in tables]}')
    
    # Check users
    try:
        users = conn.execute('SELECT id, email, name, is_admin FROM user').fetchall()
        print(f'\nUsers ({len(users)} total):')
        for user in users:
            print(f'  - ID: {user[0]}, Email: {user[1]}, Name: {user[2]}, Admin: {user[3]}')
    except Exception as e:
        print(f'Error checking users: {e}')
    
    # Check applications
    try:
        apps = conn.execute('SELECT COUNT(*) FROM application').fetchone()
        print(f'\nApplications: {apps[0]}')
        
        # Show some application details
        app_details = conn.execute('SELECT id, user_id, learnership_id, status, created_at FROM application LIMIT 5').fetchall()
        print('Recent applications:')
        for app in app_details:
            print(f'  - App ID: {app[0]}, User: {app[1]}, Learnership: {app[2]}, Status: {app[3]}, Date: {app[4]}')
    except Exception as e:
        print(f'Error checking applications: {e}')
    
    # Check companies
    try:
        companies = conn.execute('SELECT COUNT(*) FROM company').fetchone()
        print(f'\nCompanies: {companies[0]}')
    except Exception as e:
        print(f'Error checking companies: {e}')
    
    # Check learnerships
    try:
        learnerships = conn.execute('SELECT COUNT(*) FROM learnership').fetchone()
        print(f'Learnerships: {learnerships[0]}')
    except Exception as e:
        print(f'Error checking learnerships: {e}')
    
    conn.close()
else:
    print('Database not found')
