"""
modules/database.py
All database operations: init, auth, sessions, tokens, activity logging,
draft session persistence, and extended session metadata.

DATABASE BACKEND
────────────────
By default uses SQLite (file: datalyze.db or $DATALYZE_DB_PATH).
Set DATABASE_URL=postgresql://user:pass@host/dbname to switch to PostgreSQL
when deploying online (requires psycopg2: pip install psycopg2-binary).

Password hashing uses PBKDF2-HMAC-SHA256 with a random salt (bcrypt-grade
security). Existing SHA-256 unsalted hashes continue to work via fallback.
"""

import json
import uuid
import os
import hashlib
import hmac
import datetime

DB_PATH    = os.environ.get("DATALYZE_DB_PATH", "datalyze.db")
DB_URL     = os.environ.get("DATABASE_URL", "")
_PG        = DB_URL.startswith(("postgresql://", "postgres://"))


# ─── Backend-agnostic connection ─────────────────────────────────────────────

def _connect():
    if _PG:
        import psycopg2
        conn = psycopg2.connect(DB_URL)
        conn.autocommit = False
        return conn
    else:
        import sqlite3
        return sqlite3.connect(DB_PATH)


def _ph(sql: str) -> str:
    """Return correct placeholder: %s for Postgres, ? for SQLite."""
    if _PG:
        import re
        return re.sub(r"\?", "%s", sql)
    return sql


def _last_id(cursor) -> int:
    if _PG:
        cursor.execute("SELECT lastval()")
        return cursor.fetchone()[0]
    return cursor.lastrowid


# ─── Schema (CREATE IF NOT EXISTS) ───────────────────────────────────────────

def init_db():
    conn = _connect()
    c    = conn.cursor()

    if _PG:
        c.execute("""CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("""CREATE TABLE IF NOT EXISTS sessions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            session_name TEXT NOT NULL,
            file_name TEXT,
            rows_count INTEGER,
            cols_count INTEGER,
            analysis_types TEXT,
            charts_json TEXT,
            dashboard_title TEXT DEFAULT '',
            kpis_json TEXT DEFAULT '[]',
            layout_mode TEXT DEFAULT 'portrait',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id))""")
        c.execute("""CREATE TABLE IF NOT EXISTS user_activity (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            session_id INTEGER,
            action_type TEXT NOT NULL,
            action_detail TEXT,
            ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("""CREATE TABLE IF NOT EXISTS login_tokens (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            expires_at TIMESTAMP NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS draft_sessions (
            user_id INTEGER PRIMARY KEY,
            page TEXT DEFAULT 'home',
            charts_json TEXT DEFAULT '[]',
            file_name TEXT DEFAULT '',
            editing_session_id INTEGER,
            editing_session_name TEXT,
            dashboard_title TEXT DEFAULT '',
            kpis_json TEXT DEFAULT '[]',
            chart_meta_json TEXT DEFAULT '{}',
            layout_mode TEXT DEFAULT 'portrait',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id))""")
    else:
        import sqlite3
        c.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("""CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            session_name TEXT NOT NULL,
            file_name TEXT,
            rows_count INTEGER,
            cols_count INTEGER,
            analysis_types TEXT,
            charts_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id))""")
        c.execute("""CREATE TABLE IF NOT EXISTS user_activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            session_id INTEGER,
            action_type TEXT NOT NULL,
            action_detail TEXT,
            ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("""CREATE TABLE IF NOT EXISTS login_tokens (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            expires_at TIMESTAMP NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS draft_sessions (
            user_id INTEGER PRIMARY KEY,
            page TEXT DEFAULT 'home',
            charts_json TEXT DEFAULT '[]',
            file_name TEXT DEFAULT '',
            editing_session_id INTEGER,
            editing_session_name TEXT,
            dashboard_title TEXT DEFAULT '',
            kpis_json TEXT DEFAULT '[]',
            chart_meta_json TEXT DEFAULT '{}',
            layout_mode TEXT DEFAULT 'portrait',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id))""")
        # Migrate older SQLite DBs that lack the extra columns
        for col_def in [
            "ALTER TABLE sessions ADD COLUMN dashboard_title TEXT DEFAULT ''",
            "ALTER TABLE sessions ADD COLUMN kpis_json TEXT DEFAULT '[]'",
            "ALTER TABLE sessions ADD COLUMN layout_mode TEXT DEFAULT 'portrait'",
        ]:
            try:
                c.execute(col_def)
            except Exception:
                pass

    conn.commit()
    conn.close()


# ─── Password hashing (PBKDF2-HMAC-SHA256 with salt) ─────────────────────────

def _hash(pw: str, salt: str | None = None) -> str:
    """Return 'salt$hash' string. Falls back to bare sha256 for legacy rows."""
    if salt is None:
        salt = uuid.uuid4().hex
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 260_000)
    return f"{salt}${dk.hex()}"


def _verify(pw: str, stored: str) -> bool:
    """Verify password against stored hash (supports both old and new format)."""
    if "$" in stored:
        salt, _ = stored.split("$", 1)
        return hmac.compare_digest(_hash(pw, salt), stored)
    # Legacy: bare sha256 (no salt) — still accept but upgrade on next login
    return hmac.compare_digest(hashlib.sha256(pw.encode()).hexdigest(), stored)


# ─── Auth ─────────────────────────────────────────────────────────────────────

def log_activity(user_id, action_type, detail="", session_id=None):
    try:
        conn = _connect()
        conn.execute(
            _ph("INSERT INTO user_activity (user_id, session_id, action_type, action_detail) VALUES (?,?,?,?)"),
            (user_id, session_id, action_type, str(detail)[:1000]))
        conn.commit()
        conn.close()
    except Exception:
        pass


def register_user(username, email, password):
    conn = _connect()
    try:
        conn.execute(
            _ph("INSERT INTO users (username, email, password_hash) VALUES (?,?,?)"),
            (username, email, _hash(password)))
        conn.commit()
        return True, "Account created!"
    except Exception as e:
        msg = str(e)
        if "username" in msg.lower(): return False, "Username already taken."
        if "email"    in msg.lower(): return False, "Email already registered."
        return False, msg
    finally:
        conn.close()


def login_user(username, password):
    conn = _connect()
    c = conn.cursor()
    c.execute(
        _ph("SELECT id, username, password_hash FROM users WHERE username=?"),
        (username,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    uid, uname, stored_hash = row
    if not _verify(password, stored_hash):
        return None
    # Upgrade legacy bare-sha256 hashes transparently
    if "$" not in stored_hash:
        try:
            upd = _connect()
            upd.execute(_ph("UPDATE users SET password_hash=? WHERE id=?"),
                        (_hash(password), uid))
            upd.commit(); upd.close()
        except Exception:
            pass
    return uid, uname


def create_token(user_id, username):
    token   = uuid.uuid4().hex
    expires = (datetime.datetime.utcnow() + datetime.timedelta(days=7)).isoformat()
    conn = _connect()
    conn.execute(
        _ph("INSERT INTO login_tokens (token, user_id, username, expires_at) VALUES (?,?,?,?) "
            "ON CONFLICT(token) DO UPDATE SET expires_at=EXCLUDED.expires_at") if _PG else
        _ph("INSERT OR REPLACE INTO login_tokens (token, user_id, username, expires_at) VALUES (?,?,?,?)"),
        (token, user_id, username, expires))
    conn.commit()
    conn.close()
    return token


def validate_token(token):
    if not token:
        return None
    conn = _connect()
    c = conn.cursor()
    c.execute(_ph("SELECT user_id, username, expires_at FROM login_tokens WHERE token=?"), (token,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    if datetime.datetime.utcnow().isoformat() > str(row[2]):
        return None
    return row[0], row[1]


def revoke_token(token):
    conn = _connect()
    conn.execute(_ph("DELETE FROM login_tokens WHERE token=?"), (token,))
    conn.commit()
    conn.close()


# ── Draft persistence ─────────────────────────────────────────────────────────
def save_draft(user_id, page, charts_json, file_name="",
               editing_session_id=None, editing_session_name=None,
               dashboard_title="", kpis_json="[]",
               chart_meta_json="{}", layout_mode="portrait"):
    try:
        conn = _connect()
        if _PG:
            conn.execute("""INSERT INTO draft_sessions
                (user_id, page, charts_json, file_name, editing_session_id,
                 editing_session_name, dashboard_title, kpis_json,
                 chart_meta_json, layout_mode, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    page=EXCLUDED.page, charts_json=EXCLUDED.charts_json,
                    file_name=EXCLUDED.file_name,
                    editing_session_id=EXCLUDED.editing_session_id,
                    editing_session_name=EXCLUDED.editing_session_name,
                    dashboard_title=EXCLUDED.dashboard_title,
                    kpis_json=EXCLUDED.kpis_json,
                    chart_meta_json=EXCLUDED.chart_meta_json,
                    layout_mode=EXCLUDED.layout_mode,
                    updated_at=CURRENT_TIMESTAMP""",
                (user_id, page, charts_json, file_name,
                 editing_session_id, editing_session_name,
                 dashboard_title, kpis_json, chart_meta_json, layout_mode))
        else:
            conn.execute("""INSERT OR REPLACE INTO draft_sessions
                (user_id, page, charts_json, file_name, editing_session_id,
                 editing_session_name, dashboard_title, kpis_json,
                 chart_meta_json, layout_mode, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)""",
                (user_id, page, charts_json, file_name,
                 editing_session_id, editing_session_name,
                 dashboard_title, kpis_json, chart_meta_json, layout_mode))
        conn.commit()
        conn.close()
    except Exception:
        pass


def get_draft(user_id):
    try:
        conn = _connect()
        c = conn.cursor()
        c.execute(_ph("SELECT * FROM draft_sessions WHERE user_id=?"), (user_id,))
        row = c.fetchone()
        conn.close()
        if not row:
            return None
        keys = ["user_id", "page", "charts_json", "file_name",
                "editing_session_id", "editing_session_name",
                "dashboard_title", "kpis_json", "chart_meta_json",
                "layout_mode", "updated_at"]
        return dict(zip(keys, row))
    except Exception:
        return None


def clear_draft(user_id):
    try:
        conn = _connect()
        conn.execute(_ph("DELETE FROM draft_sessions WHERE user_id=?"), (user_id,))
        conn.commit()
        conn.close()
    except Exception:
        pass


# ── Sessions CRUD ─────────────────────────────────────────────────────────────
def save_session_db(user_id, session_name, file_name, rows, cols,
                    analysis_types, charts_json,
                    dashboard_title="", kpis_json="[]", layout_mode="portrait"):
    conn = _connect()
    c = conn.cursor()
    c.execute(
        _ph("""INSERT INTO sessions
           (user_id,session_name,file_name,rows_count,cols_count,
            analysis_types,charts_json,dashboard_title,kpis_json,layout_mode)
           VALUES (?,?,?,?,?,?,?,?,?,?)"""),
        (user_id, session_name, file_name, rows, cols,
         json.dumps(analysis_types), charts_json,
         dashboard_title, kpis_json, layout_mode))
    conn.commit()
    sid = _last_id(c)
    conn.close()
    log_activity(user_id, "dashboard_saved",
                 f"session='{session_name}' file='{file_name}'", sid)
    return sid


def rename_session_db(session_id, new_name, user_id=None):
    conn = _connect()
    if user_id is None:
        conn.execute(_ph("UPDATE sessions SET session_name=? WHERE id=?"), (new_name, session_id))
    else:
        conn.execute(_ph("UPDATE sessions SET session_name=? WHERE id=? AND user_id=?"),
                     (new_name, session_id, user_id))
    conn.commit()
    conn.close()


def delete_session_db(session_id, user_id):
    conn = _connect()
    conn.execute(_ph("DELETE FROM sessions WHERE id=? AND user_id=?"), (session_id, user_id))
    conn.commit()
    conn.close()
    log_activity(user_id, "session_deleted", f"session_id={session_id}")


def update_session_db(session_id, session_name, charts_json, analysis_types,
                      user_id, dashboard_title="", kpis_json="[]", layout_mode="portrait"):
    conn = _connect()
    conn.execute(
        _ph("""UPDATE sessions
           SET session_name=?, charts_json=?, analysis_types=?,
               dashboard_title=?, kpis_json=?, layout_mode=?
           WHERE id=? AND user_id=?"""),
        (session_name, charts_json, json.dumps(analysis_types),
         dashboard_title, kpis_json, layout_mode,
         session_id, user_id))
    conn.commit()
    conn.close()
    log_activity(user_id, "session_updated",
                 f"session_id={session_id} name='{session_name}'")


def get_user_sessions(user_id):
    conn = _connect()
    c = conn.cursor()
    c.execute(
        _ph("""SELECT id, session_name, file_name, rows_count, cols_count,
                  analysis_types, created_at
           FROM sessions WHERE user_id=? ORDER BY created_at DESC LIMIT 20"""),
        (user_id,))
    rows = c.fetchall()
    conn.close()
    return rows


def get_session_meta(session_id, user_id=None):
    try:
        conn = _connect()
        c = conn.cursor()
        if user_id is None:
            c.execute(
                _ph("SELECT dashboard_title, kpis_json, layout_mode FROM sessions WHERE id=?"),
                (session_id,))
        else:
            c.execute(
                _ph("""SELECT dashboard_title, kpis_json, layout_mode
                       FROM sessions WHERE id=? AND user_id=?"""),
                (session_id, user_id))
        row = c.fetchone()
        conn.close()
        if row:
            return {
                "dashboard_title": row[0] or "",
                "kpis_json":       row[1] or "[]",
                "layout_mode":     row[2] or "portrait",
            }
    except Exception:
        pass
    return None


def get_session_charts(session_id, user_id=None):
    """
    Returns list of (uid, title, fig, desc, auto_insights, chart_type, meta).
    Pure data function — callers are responsible for updating session_state.
    """
    import plotly.io as pio
    conn = _connect()
    c = conn.cursor()
    if user_id is None:
        c.execute(_ph("SELECT charts_json FROM sessions WHERE id=?"), (session_id,))
    else:
        c.execute(_ph("SELECT charts_json FROM sessions WHERE id=? AND user_id=?"),
                  (session_id, user_id))
    row = c.fetchone()
    conn.close()
    if not (row and row[0]):
        return []
    charts = []
    for item in json.loads(row[0]):
        try:
            uid           = item.get("uid", uuid.uuid4().hex[:8])
            desc          = item.get("desc", "")
            auto_insights = item.get("auto_insights", [])
            chart_type    = item.get("chart_type", "")
            meta          = item.get("meta", {})
            fig           = pio.from_json(item["fig_json"])
            charts.append((uid, item["title"], fig, desc,
                           auto_insights, chart_type, meta))
        except Exception:
            pass
    return charts
