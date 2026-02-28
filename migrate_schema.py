import psycopg2

DB_HOST = "aws-1-eu-central-1.pooler.supabase.com"
DB_PORT = "5432"
DB_USER = "postgres.tboetcmuulusvklvvswv"
DB_PASSWORD = "KfcSuperNewPass2026!"
DB_NAME = "postgres"

SCHEMA_SQL = """
-- ═══════════════════════════════════════════════
-- ORDERS
-- ═══════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    address TEXT NOT NULL,
    items JSONB NOT NULL,
    total INTEGER NOT NULL,
    status TEXT DEFAULT 'pending',
    tg_user_id BIGINT,
    phone TEXT,
    customer_name TEXT,
    coins_used INTEGER DEFAULT 0,
    payment TEXT DEFAULT 'naqt',
    extra_phone TEXT,
    comment TEXT,
    tg_msg_id BIGINT
);

CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_phone ON orders(phone);

-- ═══════════════════════════════════════════════
-- ORDER COUNTER
-- ═══════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS order_counter (
    id INTEGER PRIMARY KEY DEFAULT 1,
    last_number INTEGER DEFAULT 0
);
INSERT INTO order_counter (id, last_number) VALUES (1, 0) ON CONFLICT DO NOTHING;

-- ═══════════════════════════════════════════════
-- TELEGRAM USERS
-- ═══════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS telegram_users (
    phone TEXT PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    username TEXT,
    full_name TEXT,
    coins INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ═══════════════════════════════════════════════
-- OTP CODES
-- ═══════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS otp_codes (
    phone TEXT PRIMARY KEY,
    code TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    mode TEXT DEFAULT 'login',
    attempts INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ═══════════════════════════════════════════════
-- REGISTERED USERS
-- ═══════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS registered_users (
    phone TEXT PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ═══════════════════════════════════════════════
-- COINS TRANSACTIONS
-- ═══════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS coins_transactions (
    id SERIAL PRIMARY KEY,
    phone TEXT NOT NULL,
    amount INTEGER NOT NULL,
    order_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_coins_phone ON coins_transactions(phone);

-- ═══════════════════════════════════════════════
-- MENU CATEGORIES
-- ═══════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS menu_categories (
    id SERIAL PRIMARY KEY,
    slug TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    image_emoji TEXT,
    image_url TEXT DEFAULT ''
);

-- ═══════════════════════════════════════════════
-- MENU FOODS
-- ═══════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS menu_foods (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    full_name TEXT,
    description TEXT DEFAULT '',
    price INTEGER NOT NULL,
    category_id INTEGER REFERENCES menu_categories(id),
    image_emoji TEXT,
    image_url TEXT DEFAULT '',
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_foods_category_id ON menu_foods(category_id);
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
    print("Executing schema setup...")
    cursor.execute(SCHEMA_SQL)
    print("Schema created successfully!")
    conn.close()

if __name__ == "__main__":
    main()
