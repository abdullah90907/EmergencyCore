import sqlite3
from contextlib import closing
from pathlib import Path
from flask import current_app, g

def connect():
    conn = sqlite3.connect(current_app.config['DATABASE_PATH'], timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    return conn

def get_db():
    if 'db' not in g:
        g.db = connect()
    return g.db

def init_database(app):
    Path(app.config['DATABASE_PATH']).parent.mkdir(parents=True, exist_ok=True)
    with app.app_context():
        with closing(connect()) as conn:
            conn.executescript('''PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS incidents (
                id TEXT PRIMARY KEY, description TEXT NOT NULL, location TEXT NOT NULL,
                latitude REAL, longitude REAL, urgency TEXT NOT NULL, status TEXT NOT NULL,
                analysis TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL);''')
    
    @app.teardown_appcontext
    def close_db(_error):
        if 'db' in g:
            g.pop('db').close()
