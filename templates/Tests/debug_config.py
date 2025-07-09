from app import app

print("=== DEBUG CONFIG ===")
print(f"Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")

# Check if it's PostgreSQL or SQLite
if 'postgresql' in app.config['SQLALCHEMY_DATABASE_URI']:
    print("✅ Using PostgreSQL (Supabase)")
elif 'sqlite' in app.config['SQLALCHEMY_DATABASE_URI']:
    print("❌ Still using SQLite!")
else:
    print("❓ Unknown database type")