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
CREATE TABLE IF NOT EXISTS banned_users (
    id SERIAL PRIMARY KEY,
    phone TEXT UNIQUE NOT NULL,
    reason TEXT,
    banned_at TIMESTAMPTZ DEFAULT NOW(),
    banned_by BIGINT,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_banned_users_phone ON banned_users(phone);
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
    print("Executing schema setup for banned_users...")
    cursor.execute(SCHEMA_SQL)
    print("Table banned_users created successfully!")
    conn.close()

if __name__ == "__main__":
    main()
