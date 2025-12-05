# reset_db.py
import os
from app import app, db
from models import User, Learnership, LearnshipEmail, Application, EmailApplication, Document, ApplicationDocument, GoogleToken

def reset_database():
    with app.app_context():
        print("Dropping all tables...")
        db.drop_all()
        
        print("Creating all tables...")
        db.create_all()
        
        print("Database reset complete!")
        
        # Verify the application table structure
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        columns = inspector.get_columns('application')
        
        print("\nApplication table columns:")
        for column in columns:
            print(f"  - {column['name']}: {column['type']}")
        
        print("\nAll tables created:")
        for table_name in inspector.get_table_names():
            print(f"  - {table_name}")

if __name__ == '__main__':
    reset_database()