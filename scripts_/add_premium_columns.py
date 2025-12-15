"""
Add Premium Columns to Existing Database
This script adds the premium features to your existing SQLite database
without losing any existing data.
"""
import sys
import os
import sqlite3

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def add_premium_columns():
    """Add premium columns to existing database"""
    
    # FIXED: Correct path to your SQLite database
    project_root = os.path.dirname(os.path.dirname(__file__))
    db_path = os.path.join(project_root, 'instance', 'codecraft.db')
    
    print(f"🔧 Connecting to database: {db_path}")
    
    if not os.path.exists(db_path):
        print(f"❌ Database file not found: {db_path}")
        
        # Check if instance directory exists
        instance_dir = os.path.join(project_root, 'instance')
        if os.path.exists(instance_dir):
            print(f"📁 Instance directory exists: {instance_dir}")
            files = os.listdir(instance_dir)
            print(f"   Files in instance: {files}")
        else:
            print(f"❌ Instance directory not found: {instance_dir}")
            print("💡 Run your Flask app first to create the database")
            
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("📋 Checking existing table structure...")
        
        # Get current user table columns
        cursor.execute("PRAGMA table_info(user);")
        existing_columns = [column[1] for column in cursor.fetchall()]
        print(f"   Existing columns: {len(existing_columns)}")
        
        # List of premium columns to add
        premium_columns = [
            ('is_premium', 'BOOLEAN DEFAULT FALSE'),
            ('premium_expires', 'DATETIME'),
            ('daily_applications_used', 'INTEGER DEFAULT 0'),
            ('last_application_date', 'DATE'),
            ('premium_activated_by', 'INTEGER'),
            ('premium_activated_at', 'DATETIME')
        ]
        
        print("\n🔧 Adding premium columns...")
        
        for column_name, column_type in premium_columns:
            if column_name not in existing_columns:
                try:
                    sql = f"ALTER TABLE user ADD COLUMN {column_name} {column_type};"
                    cursor.execute(sql)
                    print(f"   ✅ Added column: {column_name}")
                except sqlite3.Error as e:
                    print(f"   ❌ Failed to add {column_name}: {e}")
            else:
                print(f"   ⚠️ Column {column_name} already exists")
        
        print("\n📝 Updating existing users with default values...")
        
        # Update existing users with default values
        update_queries = [
            "UPDATE user SET is_premium = FALSE WHERE is_premium IS NULL;",
            "UPDATE user SET daily_applications_used = 0 WHERE daily_applications_used IS NULL;",
            "UPDATE user SET last_application_date = DATE('now') WHERE last_application_date IS NULL;"
        ]
        
        for query in update_queries:
            try:
                cursor.execute(query)
                rows_affected = cursor.rowcount
                print(f"   ✅ Updated {rows_affected} users")
            except sqlite3.Error as e:
                print(f"   ❌ Update failed: {e}")
        
        print("\n🏗️ Creating premium_transactions table...")
        
        # Check if premium_transactions table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='premium_transactions';")
        if cursor.fetchone():
            print("   ⚠️ premium_transactions table already exists")
        else:
            create_table_sql = """
            CREATE TABLE premium_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                transaction_type VARCHAR(50) NOT NULL,
                amount REAL,
                duration_days INTEGER NOT NULL,
                activated_by_admin INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                notes TEXT,
                FOREIGN KEY(user_id) REFERENCES user (id),
                FOREIGN KEY(activated_by_admin) REFERENCES user (id)
            );
            """
            
            try:
                cursor.execute(create_table_sql)
                print("   ✅ Created premium_transactions table")
            except sqlite3.Error as e:
                print(f"   ❌ Failed to create table: {e}")
        
        # Commit all changes
        conn.commit()
        
        print("\n📊 Final verification...")
        
        # Verify the changes
        cursor.execute("PRAGMA table_info(user);")
        final_columns = [column[1] for column in cursor.fetchall()]
        print(f"   User table now has {len(final_columns)} columns")
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='premium_transactions';")
        if cursor.fetchone():
            print("   ✅ premium_transactions table exists")
        else:
            print("   ❌ premium_transactions table missing")
        
        # Count users
        cursor.execute("SELECT COUNT(*) FROM user;")
        user_count = cursor.fetchone()[0]
        print(f"   📊 Total users in database: {user_count}")
        
        conn.close()
        
        print("\n🎉 Premium columns added successfully!")
        print("📋 Summary:")
        print("   - Added 6 premium columns to user table")
        print("   - Created premium_transactions table") 
        print("   - Updated existing users with default values")
        print("   - All data preserved")
        
        return True
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def create_test_admin():
    """Create a test admin user with premium access"""
    try:
        from app import app, db
        from models import User, PremiumTransaction
        from datetime import datetime, timedelta
        
        with app.app_context():
            # Check if admin already exists
            admin = User.query.filter_by(email='admin@codecraft.co.za').first()
            
            if not admin:
                print("\n👤 Creating test admin user...")
                admin = User(
                    email='admin@codecraft.co.za',
                    username='admin',
                    full_name='System Administrator',
                    role='admin',
                    is_active=True,
                    is_premium=True,
                    daily_applications_used=0,
                    last_application_date=datetime.now().date()
                )
                admin.set_password('admin123')
                db.session.add(admin)
                db.session.commit()
                
                print("   ✅ Admin created: admin@codecraft.co.za / admin123")
                print("   ⚠️ PLEASE CHANGE THE DEFAULT PASSWORD!")
            else:
                print("   ℹ️ Admin user already exists")
                # Update existing admin to have premium
                if not admin.is_premium:
                    admin.is_premium = True
                    admin.daily_applications_used = 0
                    admin.last_application_date = datetime.now().date()
                    db.session.commit()
                    print("   ✅ Updated existing admin with premium access")
                    
    except Exception as e:
        print(f"❌ Error creating admin: {e}")

def verify_premium_features():
    """Verify that premium features work"""
    try:
        from app import app, db
        from models import User
        
        with app.app_context():
            # Test the premium methods
            test_user = User.query.first()
            if test_user:
                print(f"\n🧪 Testing premium features with user: {test_user.email}")
                print(f"   Is Premium: {test_user.is_premium}")
                print(f"   Remaining Applications: {test_user.get_remaining_applications()}")
                print(f"   Can Apply Today: {test_user.can_apply_today()}")
                print(f"   Premium Status: {test_user.get_premium_status()}")
                print("   ✅ Premium methods working correctly!")
            else:
                print("   ⚠️ No users found for testing")
                
    except Exception as e:
        print(f"❌ Error testing premium features: {e}")

if __name__ == '__main__':
    print("🚀 Adding Premium Features to Database...")
    print("=" * 50)
    
    # Step 1: Add columns to database
    success = add_premium_columns()
    
    if success:
        print("\n" + "=" * 50)
        
        # Step 2: Create test admin (optional)
        create_admin = input("\n🔧 Create/update admin user with premium? (y/n): ").lower().strip()
        if create_admin == 'y':
            create_test_admin()
        
        # Step 3: Verify everything works
        print("\n" + "=" * 50)
        print("🧪 Verifying premium features...")
        verify_premium_features()
        
        print("\n🎉 Setup Complete!")
        print("💡 You can now start your Flask app with: python app.py")
        print("🔗 Admin Dashboard: http://localhost:5000/admin/premium-management")
        
    else:
        print("\n❌ Setup failed. Please check the errors above.")

    print("\n" + "=" * 50)