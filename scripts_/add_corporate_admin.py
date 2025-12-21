"""
Script to add a corporate admin user for testing
"""
import os
import sys

# Add the parent directory to sys.path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import User
from datetime import datetime
import uuid

def add_corporate_admin():
    """Add a test corporate admin user"""
    with app.app_context():
        try:
            # Check if corporate admin already exists
            existing_corporate = User.query.filter_by(
                email='corporate@testcompany.com'
            ).first()
            
            if existing_corporate:
                print("✅ Corporate admin already exists:")
                print(f"   Email: {existing_corporate.email}")
                print(f"   Username: {existing_corporate.username}")
                print(f"   Company: {existing_corporate.company_name}")
                print(f"   Verified: {existing_corporate.is_verified}")
                return existing_corporate
            
            # Create corporate admin user
            corporate_admin = User(
                email='corporate@testcompany.com',
                full_name='John Smith',
                username='testcorp_admin',
                role='corporate',
                company_name='Test Corporation Ltd',
                company_email='corporate@testcompany.com',
                contact_person='John Smith',
                company_phone='+27 11 123 4567',
                company_website='https://testcorporation.co.za',
                company_address='123 Business Street, Sandton, Johannesburg, 2196',
                is_verified=True,  # Pre-verified for testing
                auth_method='corporate_form',
                created_at=datetime.utcnow(),
                last_login=None,
                is_active=True
            )
            
            # Set password
            corporate_admin.set_password('CorporateTest123!')
            
            # Add to database
            db.session.add(corporate_admin)
            db.session.commit()
            
            print("✅ Corporate admin user created successfully!")
            print("=" * 50)
            print("🔐 LOGIN CREDENTIALS:")
            print(f"   Email: corporate@testcompany.com")
            print(f"   Username: testcorp_admin")
            print(f"   Password: CorporateTest123!")
            print("=" * 50)
            print("🏢 COMPANY DETAILS:")
            print(f"   Company Name: {corporate_admin.company_name}")
            print(f"   Contact Person: {corporate_admin.contact_person}")
            print(f"   Phone: {corporate_admin.company_phone}")
            print(f"   Website: {corporate_admin.company_website}")
            print(f"   Address: {corporate_admin.company_address}")
            print(f"   Verified: {corporate_admin.is_verified}")
            print("=" * 50)
            print("🚀 NEXT STEPS:")
            print("1. Go to /admin-login")
            print("2. Login with the credentials above")
            print("3. You'll be redirected to the corporate dashboard")
            print("4. Start posting learnership opportunities!")
            
            return corporate_admin
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error creating corporate admin: {e}")
            import traceback
            traceback.print_exc()
            return None

def add_regular_admin():
    """Add a regular admin user for comparison"""
    with app.app_context():
        try:
            # Check if admin already exists
            existing_admin = User.query.filter_by(
                email='admin@codecraft.com'
            ).first()
            
            if existing_admin:
                print("✅ Regular admin already exists:")
                print(f"   Email: {existing_admin.email}")
                print(f"   Username: {existing_admin.username}")
                return existing_admin
            
            # Create regular admin user
            regular_admin = User(
                email='admin@codecraft.com',
                full_name='CodeCraft Admin',
                username='admin_main',
                role='admin',
                auth_method='manual',
                created_at=datetime.utcnow(),
                is_active=True
            )
            
            # Set password
            regular_admin.set_password('AdminPass123!')
            
            # Add to database
            db.session.add(regular_admin)
            db.session.commit()
            
            print("✅ Regular admin user created successfully!")
            print("🔐 ADMIN CREDENTIALS:")
            print(f"   Email: admin@codecraft.com")
            print(f"   Username: admin_main")
            print(f"   Password: AdminPass123!")
            
            return regular_admin
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error creating regular admin: {e}")
            return None

def show_existing_users():
    """Show existing admin and corporate users"""
    with app.app_context():
        try:
            # Get all admin and corporate users
            admin_users = User.query.filter(
                User.role.in_(['admin', 'corporate'])
            ).all()
            
            if not admin_users:
                print("❌ No admin or corporate users found!")
                return
            
            print("👥 EXISTING ADMIN & CORPORATE USERS:")
            print("=" * 80)
            print(f"{'EMAIL':<30} {'USERNAME':<20} {'ROLE':<10} {'VERIFIED':<10} {'COMPANY'}")
            print("-" * 80)
            
            for user in admin_users:
                email = user.email[:27] + "..." if len(user.email) > 30 else user.email
                username = user.username[:17] + "..." if len(user.username) > 20 else user.username
                company = (user.company_name or "N/A")[:20] + "..." if user.company_name and len(user.company_name) > 23 else (user.company_name or "N/A")
                verified = "✅ Yes" if getattr(user, 'is_verified', True) else "❌ No"
                
                print(f"{email:<30} {username:<20} {user.role:<10} {verified:<10} {company}")
            
            print("=" * 80)
            
        except Exception as e:
            print(f"❌ Error fetching users: {e}")

if __name__ == "__main__":
    print("🚀 CODECRAFT ADMIN USER SETUP")
    print("=" * 50)
    
    # Show existing users first
    print("1. Checking existing users...")
    show_existing_users()
    
    print("\n2. Adding regular admin (if not exists)...")
    add_regular_admin()
    
    print("\n3. Adding corporate admin (if not exists)...")
    add_corporate_admin()
    
    print("\n4. Final user list:")
    show_existing_users()
    
    print("\n🎉 Setup complete! You can now test both admin types:")
    print("   • Regular Admin: /admin-login → Admin Dashboard")
    print("   • Corporate Admin: /admin-login → Corporate Dashboard")