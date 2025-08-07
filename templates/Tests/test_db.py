from dotenv import load_dotenv
import os
import psycopg2

# Load variables from .env
load_dotenv()

# Get the DATABASE_URL from .env
database_url = os.getenv("DATABASE_URL")

print("Testing PostgreSQL connection...")

try:
    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()
    cursor.execute("SELECT version();")
    record = cursor.fetchone()
    print(f"✓ Connected successfully to: {record[0]}")
    cursor.close()
    conn.close()
except Exception as e:
    print(f"✗ Connection failed: {e}")
