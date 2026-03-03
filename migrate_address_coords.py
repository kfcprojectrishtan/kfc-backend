import psycopg2
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent / ".env")

DB_HOST = "aws-1-eu-central-1.pooler.supabase.com"
DB_PORT = "5432"
DB_USER = "postgres.tboetcmuulusvklvvswv"
DB_PASSWORD = "KfcSuperNewPass2026!"
DB_NAME = "postgres"

SCHEMA_SQL = """
ALTER TABLE orders ADD COLUMN IF NOT EXISTS lat DOUBLE PRECISION;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS lng DOUBLE PRECISION;
"""

def main():
    print("Connecting to Supabase PostgreSQL...")
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        dbname=DB_NAME
    )
    conn.autocommit = True
    cursor = conn.cursor()
    print("Executing schema update for orders lat/lng...")
    cursor.execute(SCHEMA_SQL)
    print("Columns lat/lng added successfully!")
    conn.close()

if __name__ == "__main__":
    main()
