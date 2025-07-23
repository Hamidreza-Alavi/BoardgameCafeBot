import sqlite3
from datetime import datetime

DB_PATH = "bot.db"

def get_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute('''
        CREATE TABLE IF NOT EXISTS tables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_id INTEGER,
            ordered_at TEXT NOT NULL,
            created_by INTEGER,
            FOREIGN KEY (table_id) REFERENCES tables(id)
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            item_name TEXT NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(id)
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_id INTEGER,
            started_at TEXT NOT NULL,
            created_by INTEGER,
            FOREIGN KEY (table_id) REFERENCES tables(id)
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS session_players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            player_number INTEGER,
            joined_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    ''')

    conn.commit()
    conn.close()

def add_table_if_not_exists(name):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO tables (name) VALUES (?)", (name,))
    conn.commit()
    conn.close()

def get_table_id(table_name):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM tables WHERE name=?", (table_name,))
    row = cur.fetchone()
    conn.close()
    if row:
        return row[0]
    return None

def save_order(user_id, table_name, items):
    table_id = get_table_id(table_name)
    if table_id is None:
        add_table_if_not_exists(table_name)
        table_id = get_table_id(table_name)

    conn = get_connection()
    cur = conn.cursor()
    ordered_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute(
        "INSERT INTO orders (table_id, ordered_at, created_by) VALUES (?, ?, ?)",
        (table_id, ordered_at, user_id)
    )
    order_id = cur.lastrowid
    for item in items:
        cur.execute(
            "INSERT INTO order_items (order_id, item_name) VALUES (?, ?)",
            (order_id, item)
        )
    conn.commit()
    conn.close()

def save_game(user_id, table_name, players_count):
    table_id = get_table_id(table_name)
    if table_id is None:
        add_table_if_not_exists(table_name)
        table_id = get_table_id(table_name)

    conn = get_connection()
    cur = conn.cursor()
    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute(
        "INSERT INTO sessions (table_id, started_at, created_by) VALUES (?, ?, ?)",
        (table_id, started_at, user_id)
    )
    session_id = cur.lastrowid
    for player_number in range(1, players_count + 1):
        cur.execute(
            "INSERT INTO session_players (session_id, player_number, joined_at) VALUES (?, ?, ?)",
            (session_id, player_number, started_at)
        )
    conn.commit()
    conn.close()