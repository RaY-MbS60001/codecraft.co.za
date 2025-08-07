# find_database.py
from app import app

with app.app_context():
    db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    print(f"Database URI: {db_uri}")
    
    if db_uri.startswith('sqlite:///'):
        db_path = db_uri.replace('sqlite:///', '')
        print(f"Database file path: {db_path}")
    else:
        print("Not using SQLite or path not found")