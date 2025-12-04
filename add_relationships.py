import psycopg2

def add_missing_relationships():
    conn = psycopg2.connect('postgresql://codecraftco_db_user:84u1KfAY4jHElF1ISEVw4YNbtZM51691@dpg-d1lknv6r433s73drf130-a.oregon-postgres.render.com/codecraftco_db')
    cur = conn.cursor()
    
    print(" Adding missing relationships...")
    
    # Add foreign key constraints if they don't exist
    relationships = [
        "ADD CONSTRAINT IF NOT EXISTS fk_application_user FOREIGN KEY (user_id) REFERENCES \"user\"(id)",
        "ADD CONSTRAINT IF NOT EXISTS fk_application_learnership FOREIGN KEY (learnership_id) REFERENCES learnership(id)"
    ]
    
    for rel_sql in relationships:
        try:
            cur.execute(f"ALTER TABLE application {rel_sql}")
            print(f" Added relationship: {rel_sql}")
        except Exception as e:
            print(f"  Relationship may already exist: {e}")
    
    conn.commit()
    cur.close()
    conn.close()
    print(" Relationships updated!")

if __name__ == "__main__":
    add_missing_relationships()
