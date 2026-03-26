"""
database.py — SQLite setup and all DB operations for the monitoring system.
"""

from typing import Optional
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "monitor.db")


def get_conn():
    """Return a SQLite connection with row_factory for dict-like rows."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't already exist."""
    conn = get_conn()
    cur = conn.cursor()

    # Devices table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS devices (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name     TEXT    NOT NULL,
            host     TEXT    NOT NULL,
            type     TEXT    NOT NULL DEFAULT 'http',  -- 'http' or 'ping'
            added_at TEXT    NOT NULL
        )
    """)

    # Monitor logs table (one row per check)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS monitor_logs (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id  INTEGER NOT NULL,
            status     TEXT    NOT NULL,   -- 'online' | 'offline'
            latency_ms REAL,               -- NULL when offline
            checked_at TEXT    NOT NULL,
            FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
        )
    """)

    conn.commit()
    conn.close()

    # Seed default devices if table is empty
    _seed_default_devices()


def _seed_default_devices():
    """Insert sample devices only if the devices table is empty."""
    conn = get_conn()
    cur = conn.cursor()
    count = cur.execute("SELECT COUNT(*) FROM devices").fetchone()[0]
    if count == 0:
        defaults = [
            ("Google", "https://google.com", "http"),
            ("GitHub", "https://github.com", "http"),
            ("Cloudflare DNS", "8.8.8.8", "ping"),
            ("OpenDNS", "208.67.222.222", "ping"),
        ]
        cur.executemany(
            "INSERT INTO devices (name, host, type, added_at) VALUES (?,?,?,?)",
            [(n, h, t, datetime.utcnow().isoformat()) for n, h, t in defaults],
        )
        conn.commit()
    conn.close()


# ── Device CRUD ──────────────────────────────────────────────────────────────

def add_device(name: str, host: str, type_: str) -> dict:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO devices (name, host, type, added_at) VALUES (?,?,?,?)",
        (name, host, type_, datetime.utcnow().isoformat()),
    )
    conn.commit()
    device_id = cur.lastrowid
    conn.close()
    return {"id": device_id, "name": name, "host": host, "type": type_}


def remove_device(device_id: int) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM devices WHERE id=?", (device_id,))
    affected = cur.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def get_devices() -> list:
    conn = get_conn()
    cur = conn.cursor()
    rows = cur.execute("SELECT * FROM devices").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_device(device_id: int) -> Optional[dict]:
    conn = get_conn()
    cur = conn.cursor()
    row = cur.execute("SELECT * FROM devices WHERE id=?", (device_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ── Log operations ───────────────────────────────────────────────────────────

def insert_log(device_id: int, status: str, latency_ms: Optional[float]):
    conn = get_conn()
    conn.execute(
        "INSERT INTO monitor_logs (device_id, status, latency_ms, checked_at) VALUES (?,?,?,?)",
        (device_id, status, latency_ms, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def get_logs(device_id: int, limit: int = 60) -> list:  # type: ignore
    """Return the last `limit` log entries for a device (newest first)."""
    conn = get_conn()
    cur = conn.cursor()
    rows = cur.execute(
        """SELECT * FROM monitor_logs
           WHERE device_id=?
           ORDER BY checked_at DESC
           LIMIT ?""",
        (device_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]  # oldest-first for charting


def get_latest_status(device_id: int) -> Optional[dict]:
    """Return the most recent log row for a device."""
    conn = get_conn()
    cur = conn.cursor()
    row = cur.execute(
        "SELECT * FROM monitor_logs WHERE device_id=? ORDER BY checked_at DESC LIMIT 1",
        (device_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def compute_uptime(device_id: int, window: int = 100) -> float:
    """Return uptime % over the last `window` checks (0–100)."""
    conn = get_conn()
    cur = conn.cursor()
    rows = cur.execute(
        """SELECT status FROM monitor_logs
           WHERE device_id=?
           ORDER BY checked_at DESC
           LIMIT ?""",
        (device_id, window),
    ).fetchall()
    conn.close()
    if not rows:
        return 0.0
    online = sum(1 for r in rows if r["status"] == "online")
    return round(online / len(rows) * 100, 1)
