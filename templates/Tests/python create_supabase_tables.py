import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime

# Your Supabase connection details
# You need to replace [YOUR-PASSWORD] with your actual database password
SUPABASE_URL = "postgresql://postgres.inkuwivfhqyplcuwjduu:-A.SPSKd7.AhGWS@aws-0-eu-central-1.pooler.supabase.com:6543/postgres"

# Alternative connection strings (choose based on your needs):
# Direct connection (for long-lived connections):
# SUPABASE_URL = "postgresql://postgres:[YOUR-PASSWORD]@db.inkuwivfhqyplcuwjduu.supabase.co:5432/postgres"

# Session pooler (for IPv4 networks):
# SUPABASE_URL = "postgresql://postgres.inkuwivfhqyplcuwjduu:[YOUR-PASSWORD]@aws-0-eu-central-1.pooler.supabase.com:5432/postgres"

def get_connection():
    """Create Supabase connection"""
    return psycopg2.connect(SUPABASE_URL)

def execute_sql(sql, description):
    """Execute SQL statement"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(sql)
        conn.commit()
        print(f"✅ {description}")
        return True
    except Exception as e:
        print(f"❌ Error with {description}: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

def create_all_tables():
    """Create all application tables based on your models"""
    
    # 1. User table
    user_sql = """
    CREATE TABLE IF NOT EXISTS "user" (
        id SERIAL PRIMARY KEY,
        email VARCHAR(120) UNIQUE NOT NULL,
        username VARCHAR(80) UNIQUE,
        password_hash VARCHAR(200),
        full_name VARCHAR(100),
        role VARCHAR(20) DEFAULT 'user',
        auth_method VARCHAR(20),
        profile_picture VARCHAR(500),
        phone VARCHAR(20),
        address TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP,
        is_active BOOLEAN DEFAULT TRUE,
        session_token VARCHAR(255) UNIQUE,
        session_expires TIMESTAMP,
        session_ip VARCHAR(45),
        session_user_agent VARCHAR(500)
    );
    """
    execute_sql(user_sql, "User table created")
    
    # 2. Learnership table
    learnership_sql = """
    CREATE TABLE IF NOT EXISTS learnership (
        id SERIAL PRIMARY KEY,
        title VARCHAR(200) NOT NULL,
        company VARCHAR(100) NOT NULL,
        category VARCHAR(50) NOT NULL,
        description TEXT,
        requirements TEXT,
        location VARCHAR(100),
        duration VARCHAR(50),
        stipend VARCHAR(50),
        closing_date TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_active BOOLEAN DEFAULT TRUE
    );
    """
    execute_sql(learnership_sql, "Learnership table created")
    
    # 3. Learnership Email table
    learnership_email_sql = """
    CREATE TABLE IF NOT EXISTS learnership_email (
        id SERIAL PRIMARY KEY,
        company_name VARCHAR(100) NOT NULL,
        email VARCHAR(120) UNIQUE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_active BOOLEAN DEFAULT TRUE
    );
    """
    execute_sql(learnership_email_sql, "Learnership Email table created")
    
    # 4. Application table
    application_sql = """
    CREATE TABLE IF NOT EXISTS application (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
        learnership_id INTEGER REFERENCES learnership(id) ON DELETE CASCADE,
        company_name VARCHAR(255),
        learnership_name VARCHAR(255),
        status VARCHAR(50) DEFAULT 'pending',
        submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    execute_sql(application_sql, "Application table created")
    
    # 5. Email Application table
    email_application_sql = """
    CREATE TABLE IF NOT EXISTS email_application (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
        learnership_email_id INTEGER NOT NULL REFERENCES learnership_email(id) ON DELETE CASCADE,
        status VARCHAR(50) DEFAULT 'sent',
        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    execute_sql(email_application_sql, "Email Application table created")
    
    # 6. Document table
    document_sql = """
    CREATE TABLE IF NOT EXISTS document (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
        document_type VARCHAR(50) NOT NULL,
        filename VARCHAR(200) NOT NULL,
        original_filename VARCHAR(200),
        file_path VARCHAR(500),
        file_size INTEGER,
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_active BOOLEAN DEFAULT TRUE
    );
    """
    execute_sql(document_sql, "Document table created")
    
    # 7. Application Document table
    application_document_sql = """
    CREATE TABLE IF NOT EXISTS application_document (
        id SERIAL PRIMARY KEY,
        application_id INTEGER NOT NULL REFERENCES application(id) ON DELETE CASCADE,
        document_id INTEGER NOT NULL REFERENCES document(id) ON DELETE CASCADE,
        learnership_name VARCHAR(100)
    );
    """
    execute_sql(application_document_sql, "Application Document table created")
    
    # 8. Google Token table
    google_token_sql = """
    CREATE TABLE IF NOT EXISTS google_token (
        id SERIAL PRIMARY KEY,
        user_id INTEGER UNIQUE REFERENCES "user"(id) ON DELETE CASCADE,
        token_json TEXT,
        refreshed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    execute_sql(google_token_sql, "Google Token table created")

def create_indexes():
    """Create indexes for better performance"""
    
    indexes = [
        # User indexes
        ('CREATE INDEX IF NOT EXISTS idx_user_email ON "user"(email);', "User email index"),
        ('CREATE INDEX IF NOT EXISTS idx_user_username ON "user"(username);', "User username index"),
        ('CREATE INDEX IF NOT EXISTS idx_user_session_token ON "user"(session_token);', "User session token index"),
        
        # Learnership indexes
        ('CREATE INDEX IF NOT EXISTS idx_learnership_company ON learnership(company);', "Learnership company index"),
        ('CREATE INDEX IF NOT EXISTS idx_learnership_category ON learnership(category);', "Learnership category index"),
        ('CREATE INDEX IF NOT EXISTS idx_learnership_closing_date ON learnership(closing_date);', "Learnership closing date index"),
        ('CREATE INDEX IF NOT EXISTS idx_learnership_is_active ON learnership(is_active);', "Learnership active status index"),
        
        # Application indexes
        ('CREATE INDEX IF NOT EXISTS idx_application_user_id ON application(user_id);', "Application user index"),
        ('CREATE INDEX IF NOT EXISTS idx_application_learnership_id ON application(learnership_id);', "Application learnership index"),
        ('CREATE INDEX IF NOT EXISTS idx_application_status ON application(status);', "Application status index"),
        
        # Email Application indexes
        ('CREATE INDEX IF NOT EXISTS idx_email_application_user_id ON email_application(user_id);', "Email Application user index"),
        ('CREATE INDEX IF NOT EXISTS idx_email_application_learnership_email_id ON email_application(learnership_email_id);', "Email Application learnership email index"),
        
        # Document indexes
        ('CREATE INDEX IF NOT EXISTS idx_document_user_id ON document(user_id);', "Document user index"),
        ('CREATE INDEX IF NOT EXISTS idx_document_type ON document(document_type);', "Document type index"),
        
        # Application Document indexes
        ('CREATE INDEX IF NOT EXISTS idx_application_document_application_id ON application_document(application_id);', "Application Document application index"),
        ('CREATE INDEX IF NOT EXISTS idx_application_document_document_id ON application_document(document_id);', "Application Document document index"),
    ]
    
    for sql, description in indexes:
        execute_sql(sql, description)

def create_triggers():
    """Create triggers for automatic timestamp updates"""
    
    # Create update timestamp function
    update_timestamp_function = """
    CREATE OR REPLACE FUNCTION update_updated_at_column()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = CURRENT_TIMESTAMP;
        RETURN NEW;
    END;
    $$ language 'plpgsql';
    """
    execute_sql(update_timestamp_function, "Update timestamp function created")
    
    # Create trigger for application table
    application_trigger = """
    CREATE TRIGGER update_application_updated_at 
    BEFORE UPDATE ON application
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
    """
    execute_sql(application_trigger, "Application update trigger created")

def create_views():
    """Create useful views"""
    
    # View for user applications with learnership details
    user_applications_view = """
    CREATE OR REPLACE VIEW user_applications_view AS
    SELECT 
        a.id AS application_id,
        a.user_id,
        u.email AS user_email,
        u.full_name AS user_name,
        a.learnership_id,
        COALESCE(l.title, a.company_name) AS learnership_title,
        COALESCE(l.company, a.company_name) AS company,
        l.category,
        l.location,
        l.closing_date,
        a.status,
        a.submitted_at,
        a.updated_at
    FROM application a
    JOIN "user" u ON a.user_id = u.id
    LEFT JOIN learnership l ON a.learnership_id = l.id;
    """
    execute_sql(user_applications_view, "User applications view created")
    
    # View for active learnerships
    active_learnerships_view = """
    CREATE OR REPLACE VIEW active_learnerships_view AS
    SELECT 
        l.*,
        COUNT(DISTINCT a.id) AS application_count
    FROM learnership l
    LEFT JOIN application a ON l.id = a.learnership_id
    WHERE l.is_active = TRUE 
        AND (l.closing_date IS NULL OR l.closing_date > CURRENT_TIMESTAMP)
    GROUP BY l.id;
    """
    execute_sql(active_learnerships_view, "Active learnerships view created")

def insert_sample_data():
    """Insert some sample data for testing"""
    
    # Insert sample user
    sample_user = """
    INSERT INTO "user" (email, username, full_name, role, auth_method, is_active)
    VALUES 
        ('admin@example.com', 'admin', 'Admin User', 'admin', 'local', TRUE),
        ('test@example.com', 'testuser', 'Test User', 'user', 'google', TRUE)
    ON CONFLICT (email) DO NOTHING;
    """
    execute_sql(sample_user, "Sample users inserted")
    
    # Insert sample learnerships
    sample_learnerships = """
    INSERT INTO learnership (title, company, category, description, requirements, location, duration, stipend, closing_date, is_active)
    VALUES 
        ('Software Development Learnership', 'Tech Corp', 'IT', 'Learn software development skills', 'Grade 12, Basic computer skills', 'Johannesburg', '12 months', 'R5000', CURRENT_TIMESTAMP + INTERVAL '30 days', TRUE),
        ('Data Science Internship', 'Data Solutions', 'IT', 'Hands-on data science experience', 'Degree in related field', 'Cape Town', '6 months', 'R8000', CURRENT_TIMESTAMP + INTERVAL '15 days', TRUE),
        ('Business Analysis Programme', 'Finance Co', 'Business', 'Business analysis training', 'Commerce background preferred', 'Durban', '18 months', 'R6000', CURRENT_TIMESTAMP + INTERVAL '45 days', TRUE)
    ON CONFLICT DO NOTHING;
    """
    execute_sql(sample_learnerships, "Sample learnerships inserted")
    
    # Insert sample learnership emails
    sample_emails = """
    INSERT INTO learnership_email (company_name, email, is_active)
    VALUES 
        ('Tech Corp', 'hr@techcorp.com', TRUE),
        ('Data Solutions', 'careers@datasolutions.com', TRUE),
        ('Finance Co', 'recruitment@financeco.com', TRUE)
    ON CONFLICT (email) DO NOTHING;
    """
    execute_sql(sample_emails, "Sample learnership emails inserted")

def main():
    """Main function to create all database objects"""
    print("🚀 Starting Supabase database setup...")
    print("   Project: codecraftco")
    print("   Database: codecraftco-db")
    
    # Test connection first
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"✅ Connected to: {version[0]}")
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("\n⚠️  Please check that you've replaced '[YOUR-PASSWORD]' with your actual database password")
        return
    
    # Create tables
    print("\n📋 Creating tables...")
    create_all_tables()
    
    # Create indexes
    print("\n📊 Creating indexes...")
    create_indexes()
    
    # Create triggers
    print("\n⚡ Creating triggers...")
    create_triggers()
    
    # Create views
    print("\n👁️  Creating views...")
    create_views()
    
    # Insert sample data
    print("\n📝 Inserting sample data...")
    insert_sample_data()
    
    print("\n✅ Database setup completed successfully!")
    print("\n📌 Next steps:")
    print("   1. Update your Flask app's DATABASE_URL to use the Supabase connection string")
    print("   2. Update your .env file with:")
    print(f"      DATABASE_URL={SUPABASE_URL}")
    print("   3. Test your application with the new database")
    print("   4. Consider enabling Row Level Security (RLS) in Supabase for additional security")
    
    # Also provide the Flask configuration
    # Also provide the Flask configuration
    print("\n🔧 Flask Configuration Update:")
    print("   Update your Flask app configuration:")
    print("   ```python")
    print("   # In your config.py or app.py")
    print("   import os")
    print("   ")
    print("   class Config:")
    print(f'       SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or \\')
    print(f'           "postgresql://postgres.inkuwivfhqyplcuwjduu:[YOUR-PASSWORD]@aws-0-eu-central-1.pooler.supabase.com:6543/postgres"')
    print("       SQLALCHEMY_TRACK_MODIFICATIONS = False")
    print("   ```")

if __name__ == "__main__":
    main()