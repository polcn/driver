import sqlite3
import os
from pathlib import Path

DATABASE_PATH = os.getenv("DATABASE_PATH", "/data/driver.db")


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    schema_path = Path(__file__).parent.parent / "schema.sql"
    conn = get_db()
    with open(schema_path, "r") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
