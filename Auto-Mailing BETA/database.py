import sqlite3


DB_NAME = "bot.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            language TEXT,
            subscribed INTEGER DEFAULT 0,
            prem INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            user_id INTEGER,
            phone TEXT,
            session_name TEXT,
            active INTEGER DEFAULT 1,
            username TEXT,
            first_name TEXT,
            PRIMARY KEY (user_id, phone)
        )
    """)

    # --- миграции ---
    cursor.execute("PRAGMA table_info(users)")
    user_cols = [row[1] for row in cursor.fetchall()]
    if "prem" not in user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN prem INTEGER DEFAULT 0")

    cursor.execute("PRAGMA table_info(accounts)")
    acc_cols = [row[1] for row in cursor.fetchall()]
    if "username" not in acc_cols:
        cursor.execute("ALTER TABLE accounts ADD COLUMN username TEXT")
    if "first_name" not in acc_cols:
        cursor.execute("ALTER TABLE accounts ADD COLUMN first_name TEXT")

    conn.commit()
    conn.close()


def get_language(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None


def save_language(user_id, language):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (user_id, language, subscribed)
        VALUES (?, ?, 0)
        ON CONFLICT(user_id)
        DO UPDATE SET language = excluded.language
    """, (user_id, language))
    conn.commit()
    conn.close()


def get_subscription(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT subscribed FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return bool(result[0]) if result else False


def save_subscription(user_id, subscribed):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (user_id, language, subscribed)
        VALUES (?, NULL, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET subscribed = excluded.subscribed
    """, (user_id, int(subscribed)))
    conn.commit()
    conn.close()


# ---------- PREM ----------

def is_prem(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT prem FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return bool(result[0]) if result else False


def set_prem(user_id, value):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (user_id, language, subscribed, prem)
        VALUES (?, NULL, 0, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET prem = excluded.prem
    """, (user_id, int(value)))
    conn.commit()
    conn.close()


# ---------- ACCOUNTS ----------

def count_user_accounts(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM accounts WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0


def get_user_accounts(user_id):
    """Возвращает список (phone, active, username, first_name)."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT phone, active, username, first_name FROM accounts "
        "WHERE user_id = ? ORDER BY phone",
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def add_user_account(user_id, phone, session_name, username=None, first_name=None):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO accounts (user_id, phone, session_name, active, username, first_name)
        VALUES (?, ?, ?, 1, ?, ?)
        ON CONFLICT(user_id, phone)
        DO UPDATE SET
            session_name = excluded.session_name,
            username = excluded.username,
            first_name = excluded.first_name
    """, (user_id, phone, session_name, username, first_name))
    conn.commit()
    conn.close()


def remove_user_account(user_id, phone):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM accounts WHERE user_id = ? AND phone = ?",
        (user_id, phone)
    )
    conn.commit()
    conn.close()


def set_account_active(user_id, phone, active):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE accounts SET active = ?
        WHERE user_id = ? AND phone = ?
    """, (int(active), user_id, phone))
    conn.commit()
    conn.close()


def get_account_session_name(user_id, phone):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT session_name FROM accounts WHERE user_id = ? AND phone = ?",
        (user_id, phone)
    )
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None