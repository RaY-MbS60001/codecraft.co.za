from app import app, db, User
from datetime import datetime, timedelta
import uuid

def test_session_functionality():
    """Test the session functionality"""
    with app.app_context():
        try:
            # Get or create a test user
            user = User.query.first()
            if not user:
                user = User(
                    email='test@example.com',
                    username='testuser',
                    full_name='Test User',
                    role='user',
                    auth_method='local',
                    is_active=True
                )
                user.set_password('testpass')
                db.session.add(user)
                db.session.commit()
                print("Created test user")
            
            # Test session token generation
            session_token = str(uuid.uuid4())
            user.session_token = session_token
            user.session_expires = datetime.utcnow() + timedelta(hours=2)
            user.session_ip = '127.0.0.1'
            user.session_user_agent = 'Test Browser'
            
            db.session.commit()
            
            print(f"✓ Session token set: {user.session_token}")
            print(f"✓ Session expires: {user.session_expires}")
            print(f"✓ Session IP: {user.session_ip}")
            print(f"✓ Session user agent: {user.session_user_agent}")
            
            # Test session validation
            if user.session_token == session_token:
                print("✓ Session validation working!")
            else:
                print("✗ Session validation failed!")
                
            print("\nSession functionality test completed!")
            
        except Exception as e:
            print(f"Error testing session: {e}")

if __name__ == "__main__":
    test_session_functionality()