"""Shared SQLite helpers. Autocommit mode — each statement commits immediately."""
import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "mocks"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def get_conn(name: str) -> sqlite3.Connection:
    conn = sqlite3.connect(DATA_DIR / f"{name}.db", isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(name: str, ddl: str) -> None:
    conn = get_conn(name)
    conn.executescript(ddl)
    conn.close()


def log(conn: sqlite3.Connection, level: str, message: str) -> None:
    conn.execute(
        "INSERT INTO logs (level, message, created_at) VALUES (?, ?, datetime('now'))",
        (level, message),
    )
