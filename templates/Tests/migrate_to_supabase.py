from app import app, db
from models import *
from sqlalchemy import text

with app.app_context():
    try:
        print("🔄 Connecting to Supabase...")

        dialect = db.engine.dialect.name
        print(f"Dialect detected: {dialect}")

        with db.engine.connect() as conn:
            if dialect == "postgresql":
                result = conn.execute(text("SELECT version();"))
                version = result.fetchone()[0]
                print(f"✅ Connected! PostgreSQL version: {version}")
            else:
                print(f"⚠️ Skipping version check (dialect = '{dialect}')")

        print("🔄 Dropping existing tables...")
        db.drop_all()

        print("🔄 Creating tables...")
        db.create_all()

        with db.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            """))
            tables = result.fetchall()
            print(f"✅ Created tables: {[table[0] for table in tables]}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
