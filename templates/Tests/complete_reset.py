# complete_reset.py
import os
from app import app, db

def complete_reset():
    with app.app_context():
        # Get database path
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        if db_uri.startswith('sqlite:///'):
            db_path = db_uri.replace('sqlite:///', '')
            
            # Delete database file if it exists
            if os.path.exists(db_path):
                os.remove(db_path)
                print(f"Deleted existing database file: {db_path}")
            
            # Create directory if it doesn't exist
            db_dir = os.path.dirname(db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir)
                print(f"Created directory: {db_dir}")
        
        # Import all models to ensure they're registered
        from models import (User, Learnership, LearnshipEmail, Application, 
                          EmailApplication, Document, ApplicationDocument, GoogleToken)
        
        print("Creating all tables...")
        db.create_all()
        
        # Verify application table structure
        import sqlite3
        if db_uri.startswith('sqlite:///'):
            db_path = db_uri.replace('sqlite:///', '')
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute("PRAGMA table_info(application)")
            columns = cursor.fetchall()
            
            print("\nApplication table structure:")
            for column in columns:
                print(f"  {column[1]} ({column[2]})")
            
            conn.close()
        
        print("Database reset complete!")

if __name__ == '__main__':
    complete_reset()