import psycopg2

def add_missing_columns():
    conn = psycopg2.connect('postgresql://codecraftco_db_user:84u1KfAY4jHElF1ISEVw4YNbtZM51691@dpg-d1lknv6r433s73drf130-a.oregon-postgres.render.com/codecraftco_db')
    cur = conn.cursor()
    
    print(" Adding missing columns to production database...")
    
    # List of columns to add to application table
    new_columns = [
        "ADD COLUMN IF NOT EXISTS sent_at TIMESTAMP",
        "ADD COLUMN IF NOT EXISTS gmail_message_id VARCHAR(255)",
        "ADD COLUMN IF NOT EXISTS gmail_thread_id VARCHAR(255)", 
        "ADD COLUMN IF NOT EXISTS email_status VARCHAR(50) DEFAULT 'draft'",
        "ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMP",
        "ADD COLUMN IF NOT EXISTS read_at TIMESTAMP",
        "ADD COLUMN IF NOT EXISTS response_received_at TIMESTAMP",
        "ADD COLUMN IF NOT EXISTS has_response BOOLEAN DEFAULT FALSE",
        "ADD COLUMN IF NOT EXISTS response_thread_count INTEGER DEFAULT 0"
    ]
    
    for column_sql in new_columns:
        try:
            cur.execute(f"ALTER TABLE application {column_sql}")
            print(f"✅ Added: {column_sql}")
        except Exception as e:
            print(f" Error with {column_sql}: {e}")
    
    # Commit changes
    conn.commit()
    
    # Verify columns were added
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'application' ORDER BY ordinal_position")
    columns = [row[0] for row in cur.fetchall()]
    
    print(f"\n Application table now has {len(columns)} columns:")
    for col in columns:
        print(f"  - {col}")
    
    cur.close()
    conn.close()
    print("\n Migration completed!")

if __name__ == "__main__":
    add_missing_columns()
