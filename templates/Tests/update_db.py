from app import app, db, User
from sqlalchemy import text

def add_session_columns():
    """Add session tracking columns to User table"""
    with app.app_context():
        try:
            # First, create all tables
            db.create_all()
            
            # Check current columns
            inspector = db.inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('user')]
            print(f"Current columns: {columns}")
            
            # Add session columns if they don't exist
            session_columns = {
                'session_token': 'VARCHAR(255)',
                'session_expires': 'DATETIME',
                'session_ip': 'VARCHAR(45)',
                'session_user_agent': 'VARCHAR(500)'
            }
            
            for col_name, col_type in session_columns.items():
                if col_name not in columns:
                    try:
                        sql = text(f"ALTER TABLE user ADD COLUMN {col_name} {col_type}")
                        db.engine.execute(sql)
                        print(f"✓ Added {col_name} column")
                    except Exception as e:
                        print(f"✗ Error adding {col_name}: {e}")
                else:
                    print(f"✓ {col_name} column already exists")
            
            print("\nDatabase update completed!")
            
            # Test the new columns
            user = User.query.first()
            if user:
                print(f"Test user found: {user.email}")
                print(f"Session token: {user.session_token}")
                print("Session columns are working!")
            else:
                print("No users found for testing")
                
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    add_session_columns()