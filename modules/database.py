"""
modules/database.py -- All database operations for Lytrize.
============================================================

Handles: schema creation, authentication, session CRUD, token management,
activity logging, and draft session persistence.

──────────────────────────────────────────────────────────────────────────────
DATABASE BACKEND
──────────────────────────────────────────────────────────────────────────────
Default: SQLite file at  lytrize.db  (or $LYTRIZE_DB_PATH).
Postgres: set DATABASE_URL=postgresql://user:pass@host/dbname in the environment.
          Requires: pip install psycopg2-binary

The module abstracts the backend difference with three helpers:
    _connect()  -- returns a new connection for either backend
    _ph(sql)    -- swaps ? → %s for Postgres
    _last_id(c) -- gets the last inserted row ID in a backend-agnostic way

──────────────────────────────────────────────────────────────────────────────
SCHEMA OVERVIEW
──────────────────────────────────────────────────────────────────────────────
  users            -- registered accounts
  sessions         -- saved analysis dashboards
  user_activity    -- append-only audit log
  login_tokens     -- persistent login tokens (7-day expiry)
  draft_sessions   -- auto-saved in-progress work (one row per user)

──────────────────────────────────────────────────────────────────────────────
PASSWORD SECURITY
──────────────────────────────────────────────────────────────────────────────
New passwords: PBKDF2-HMAC-SHA256, 260,000 iterations, random per-user salt.
Stored as:     "<salt>$<hex-digest>"
Legacy hashes: bare SHA-256 (no salt) -- still accepted, upgraded on next login.

──────────────────────────────────────────────────────────────────────────────
CONTRIBUTING -- adding a new table
──────────────────────────────────────────────────────────────────────────────
  1. Add CREATE TABLE IF NOT EXISTS blocks in init_db() for BOTH the _PG
     and SQLite branches -- keep the schemas in sync.
  2. Add CRUD functions below with clear docstrings.
  3. Import new functions in the page(s) that need them.
  4. Never call st.* in this module -- it is a pure data layer.

Bug fixes applied:
  - delete_user_db(): removed log_activity() call after user is deleted
    (the user FK no longer exists -- writing to user_activity would fail).
  - SQLite sessions table: added dashboard_title, kpis_json, layout_mode
    directly in CREATE TABLE (the ALTER TABLE migrations remain for existing DBs).
"""

import json
import uuid
import os
import hashlib
import hmac
import datetime
from typing import Optional

# ── Environment configuration ─────────────────────────────────────────────────
# Override DB_PATH via LYTRIZE_DB_PATH env var to point at a custom SQLite file.
# Override to Postgres by setting DATABASE_URL to a postgresql:// URI.
DB_PATH = os.environ.get("LYTRIZE_DB_PATH", "lytrize.db")
DB_URL  = os.environ.get("DATABASE_URL", "")
_PG     = DB_URL.startswith(("postgresql://", "postgres://"))


# ─────────────────────────────────────────────────────────────────────────────
# Backend-agnostic connection helpers
# ─────────────────────────────────────────────────────────────────────────────

def _connect():
    """
    Return a new database connection for the configured backend.

    For Postgres, autocommit is disabled so all writes require an explicit
    conn.commit(). For SQLite, check_same_thread=False allows the connection
    to be used from Streamlit's multi-threaded runner.
    """
    if _PG:
        import psycopg2
        conn = psycopg2.connect(DB_URL)
        conn.autocommit = False
        return conn
    else:
        import sqlite3
        return sqlite3.connect(DB_PATH, check_same_thread=False)


def _ph(sql: str) -> str:
    """
    Translate SQLite-style ? placeholders to Postgres %s placeholders.

    Call this on every parameterised query string:
        conn.execute(_ph("SELECT * FROM users WHERE id=?"), (uid,))
    """
    if _PG:
        import re
        return re.sub(r"\?", "%s", sql)
    return sql


def _last_id(cursor) -> int:
    """Return the last auto-generated row ID in a backend-agnostic way."""
    if _PG:
        cursor.execute("SELECT lastval()")
        return cursor.fetchone()[0]
    return cursor.lastrowid


# ─────────────────────────────────────────────────────────────────────────────
# Schema -- CREATE IF NOT EXISTS
# ─────────────────────────────────────────────────────────────────────────────

def init_db() -> None:
    """
    Create all required tables if they do not already exist.

    Safe to call on every app startup -- all statements use IF NOT EXISTS.
    For SQLite, also runs ALTER TABLE migrations to add columns introduced
    in later versions (so existing databases are upgraded automatically).

    Called once in app.py before any page is rendered.
    """
    conn = _connect()
    c    = conn.cursor()

    if _PG:
        # ── PostgreSQL schema ─────────────────────────────────────────────────
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
        # ── SQLite schema ─────────────────────────────────────────────────────
        import sqlite3

        c.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

        # FIX: dashboard_title, kpis_json, layout_mode are now included in the
        # initial CREATE TABLE statement (they were previously only added via
        # ALTER TABLE, which meant fresh databases were inconsistent with Postgres).
        c.execute("""CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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

        # Migrate existing SQLite databases that pre-date these columns.
        # Errors are silently ignored -- the column already exists in that case.
        for col_def in [
            "ALTER TABLE sessions ADD COLUMN dashboard_title TEXT DEFAULT ''",
            "ALTER TABLE sessions ADD COLUMN kpis_json TEXT DEFAULT '[]'",
            "ALTER TABLE sessions ADD COLUMN layout_mode TEXT DEFAULT 'portrait'",
        ]:
            try:
                c.execute(col_def)
            except Exception:
                pass  # Column already exists -- safe to ignore.

    conn.commit()
    conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# Password hashing
# ─────────────────────────────────────────────────────────────────────────────

def _hash(pw: str, salt: Optional[str] = None) -> str:
    """
    Hash a password using PBKDF2-HMAC-SHA256 with a random per-user salt.

    Args:
        pw:   Plain-text password.
        salt: Hex string. If None, a fresh random salt is generated.

    Returns:
        "<salt>$<hex-digest>" -- stored in users.password_hash.
    """
    if salt is None:
        salt = uuid.uuid4().hex  # 32-char random hex salt.
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 260_000)
    return f"{salt}${dk.hex()}"


def _verify(pw: str, stored: str) -> bool:
    """
    Verify a plain-text password against a stored hash.

    Supports both the new salted format ("salt$hash") and the legacy bare
    SHA-256 format (no salt) so old accounts continue to work.

    Uses hmac.compare_digest to prevent timing attacks.
    """
    if "$" in stored:
        salt, _ = stored.split("$", 1)
        return hmac.compare_digest(_hash(pw, salt), stored)
    # Legacy format: bare sha256 without salt.
    return hmac.compare_digest(hashlib.sha256(pw.encode()).hexdigest(), stored)


# ─────────────────────────────────────────────────────────────────────────────
# Activity logging
# ─────────────────────────────────────────────────────────────────────────────

def log_activity(user_id: int, action_type: str, detail: str = "",
                 session_id=None) -> None:
    """
    Append an event to the user_activity audit log.

    Silently no-ops on any error so logging failures never crash the app.
    Truncates detail to 1000 characters to protect against oversized strings.

    Args:
        user_id:     The acting user's DB ID.
        action_type: Short event type string (e.g. "dashboard_saved").
        detail:      Optional human-readable detail string.
        session_id:  Optional related session ID.
    """
    try:
        conn = _connect()
        conn.execute(
            _ph("INSERT INTO user_activity "
                "(user_id, session_id, action_type, action_detail) "
                "VALUES (?,?,?,?)"),
            (user_id, session_id, action_type, str(detail)[:1000]))
        conn.commit()
        conn.close()
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Authentication
# ─────────────────────────────────────────────────────────────────────────────

def register_user(username: str, email: str, password: str):
    """
    Create a new user account.

    Returns:
        (True, "Account created!")       on success.
        (False, "<reason>")              on failure.

    Unique constraint violations on username and email are caught and returned
    as user-friendly messages rather than raw SQL errors.
    """
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


def login_user(username: str, password: str):
    """
    Validate login credentials.

    Automatically upgrades a bare SHA-256 legacy hash to the salted PBKDF2
    format on successful login, so old accounts become more secure transparently.

    Returns:
        (user_id: int, username: str) on success.
        None on failure (wrong username or wrong password).
    """
    conn = _connect()
    c    = conn.cursor()
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
    # Upgrade legacy bare-sha256 hash to salted PBKDF2 silently.
    if "$" not in stored_hash:
        try:
            upd = _connect()
            upd.execute(
                _ph("UPDATE users SET password_hash=? WHERE id=?"),
                (_hash(password), uid))
            upd.commit()
            upd.close()
        except Exception:
            pass
    return uid, uname


def create_token(user_id: int, username: str) -> str:
    """
    Issue a new persistent login token (7-day expiry).

    Tokens are stored in login_tokens. On page refresh, app.py validates the
    token from the ?t= URL parameter to restore the session without re-login.

    Returns:
        A 32-character hex token string.
    """
    token   = uuid.uuid4().hex
    expires = (
        datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(days=7)
    ).isoformat()
    conn = _connect()
    # Postgres uses INSERT ... ON CONFLICT; SQLite uses INSERT OR REPLACE.
    conn.execute(
        _ph("INSERT INTO login_tokens (token, user_id, username, expires_at) "
            "VALUES (?,?,?,?) "
            "ON CONFLICT(token) DO UPDATE SET expires_at=EXCLUDED.expires_at")
        if _PG else
        _ph("INSERT OR REPLACE INTO login_tokens "
            "(token, user_id, username, expires_at) VALUES (?,?,?,?)"),
        (token, user_id, username, expires))
    conn.commit()
    conn.close()
    return token


def validate_token(token: str):
    """
    Validate a login token and return the associated user.

    Handles both string expiry (SQLite) and datetime expiry (Postgres)
    transparently.

    Returns:
        (user_id: int, username: str) if valid and not expired.
        None otherwise.
    """
    if not token:
        return None
    conn = _connect()
    c    = conn.cursor()
    c.execute(
        _ph("SELECT user_id, username, expires_at FROM login_tokens WHERE token=?"),
        (token,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None

    # Normalise expires_at to an aware datetime regardless of DB backend.
    expires_raw = row[2]
    if isinstance(expires_raw, datetime.datetime):
        expires_dt = (expires_raw if expires_raw.tzinfo
                      else expires_raw.replace(tzinfo=datetime.timezone.utc))
    else:
        expires_str = str(expires_raw).replace("Z", "+00:00")
        try:
            expires_dt = datetime.datetime.fromisoformat(expires_str)
        except ValueError:
            return None  # Unparseable expiry -- treat as expired.
        if expires_dt.tzinfo is None:
            expires_dt = expires_dt.replace(tzinfo=datetime.timezone.utc)

    if datetime.datetime.now(datetime.timezone.utc) >= expires_dt:
        return None  # Token has expired.

    return row[0], row[1]


def revoke_token(token: str) -> None:
    """Delete a login token (called on sign-out)."""
    conn = _connect()
    conn.execute(_ph("DELETE FROM login_tokens WHERE token=?"), (token,))
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# Draft session persistence  (auto-save / resume on page refresh)
# ─────────────────────────────────────────────────────────────────────────────

def save_draft(user_id: int, page: str, charts_json: str, file_name: str = "",
               editing_session_id=None, editing_session_name=None,
               dashboard_title: str = "", kpis_json: str = "[]",
               chart_meta_json: str = "{}", layout_mode: str = "portrait") -> None:
    """
    Upsert the user's current in-progress state to draft_sessions.

    Called by pages/dashboard.py on every meaningful state change. On the
    next page load, app.py calls get_draft() to restore this state.

    Uses INSERT OR REPLACE (SQLite) / INSERT ... ON CONFLICT DO UPDATE (PG)
    because there is at most one draft row per user.

    Args:
        user_id:              The acting user's DB ID.
        page:                 Current page slug (e.g. "analysis").
        charts_json:          JSON string from charts_to_json().
        file_name:            Active file name for display.
        editing_session_id:   DB ID of the saved session being edited, if any.
        editing_session_name: Display name of that session.
        dashboard_title:      Current dashboard title string.
        kpis_json:            JSON-encoded list of KPI dicts.
        chart_meta_json:      JSON-encoded dict of per-chart metadata keys.
        layout_mode:          "portrait" or "landscape".
    """
    try:
        conn = _connect()
        if _PG:
            conn.execute("""
                INSERT INTO draft_sessions
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
            conn.execute("""
                INSERT OR REPLACE INTO draft_sessions
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


def get_draft(user_id: int) -> Optional[dict]:
    """
    Retrieve the stored draft for a user.

    Returns:
        dict with keys matching draft_sessions columns, or None if no draft exists.
    """
    try:
        conn = _connect()
        c    = conn.cursor()
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


def clear_draft(user_id: int) -> None:
    """Delete the draft row for a user (called after a successful session save)."""
    try:
        conn = _connect()
        conn.execute(_ph("DELETE FROM draft_sessions WHERE user_id=?"), (user_id,))
        conn.commit()
        conn.close()
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Sessions CRUD
# ─────────────────────────────────────────────────────────────────────────────

def save_session_db(user_id: int, session_name: str, file_name: str,
                    rows: int, cols: int, analysis_types: list,
                    charts_json: str, dashboard_title: str = "",
                    kpis_json: str = "[]", layout_mode: str = "portrait") -> int:
    """
    Insert a new saved session and return its DB ID.

    Args:
        user_id:        Owner's DB ID.
        session_name:   Display name chosen by the user.
        file_name:      Name of the uploaded file.
        rows / cols:    Dataset dimensions.
        analysis_types: List of analysis ID strings run in this session.
        charts_json:    Serialised charts from charts_to_json().
        dashboard_title, kpis_json, layout_mode: Dashboard metadata.

    Returns:
        int -- the new session's DB row ID.
    """
    conn = _connect()
    c    = conn.cursor()
    c.execute(
        _ph("""INSERT INTO sessions
           (user_id, session_name, file_name, rows_count, cols_count,
            analysis_types, charts_json, dashboard_title, kpis_json, layout_mode)
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


def rename_session_db(session_id: int, new_name: str, user_id=None) -> None:
    """
    Rename a saved session.

    When user_id is provided, an extra AND user_id=? guard prevents users
    from renaming sessions belonging to other accounts.
    """
    conn = _connect()
    if user_id is None:
        conn.execute(
            _ph("UPDATE sessions SET session_name=? WHERE id=?"),
            (new_name, session_id))
    else:
        conn.execute(
            _ph("UPDATE sessions SET session_name=? WHERE id=? AND user_id=?"),
            (new_name, session_id, user_id))
    conn.commit()
    conn.close()


def delete_session_db(session_id: int, user_id: int) -> None:
    """Delete a saved session. The user_id guard prevents cross-account deletion."""
    conn = _connect()
    conn.execute(
        _ph("DELETE FROM sessions WHERE id=? AND user_id=?"),
        (session_id, user_id))
    conn.commit()
    conn.close()


def delete_user_db(user_id: int) -> bool:
    """
    Permanently delete a user account and all associated data.

    Deletes in FK-dependency order:
        login_tokens → draft_sessions → user_activity → sessions → users

    FIX: log_activity() is NOT called after deletion -- the user row no longer
    exists in `users`, so any FK constraint on user_activity would fail.

    Returns:
        True on success, False if any error occurred.
    """
    try:
        conn = _connect()
        conn.execute(_ph("DELETE FROM login_tokens   WHERE user_id=?"), (user_id,))
        conn.execute(_ph("DELETE FROM draft_sessions WHERE user_id=?"), (user_id,))
        conn.execute(_ph("DELETE FROM user_activity  WHERE user_id=?"), (user_id,))
        conn.execute(_ph("DELETE FROM sessions        WHERE user_id=?"), (user_id,))
        conn.execute(_ph("DELETE FROM users           WHERE id=?"),      (user_id,))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def update_session_db(session_id: int, session_name: str, charts_json: str,
                      analysis_types: list, user_id: int,
                      dashboard_title: str = "", kpis_json: str = "[]",
                      layout_mode: str = "portrait") -> None:
    """
    Overwrite a saved session's charts and metadata in-place.

    The user_id guard ensures only the owner can update their sessions.
    """
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


def get_user_sessions(user_id: int) -> list:
    """
    Fetch the 20 most recent sessions for a user (newest first).

    Returns:
        list of tuples: (id, session_name, file_name, rows_count, cols_count,
                         analysis_types, created_at)
    """
    conn = _connect()
    c    = conn.cursor()
    c.execute(
        _ph("""SELECT id, session_name, file_name, rows_count, cols_count,
                  analysis_types, created_at
           FROM sessions WHERE user_id=? ORDER BY created_at DESC LIMIT 20"""),
        (user_id,))
    rows = c.fetchall()
    conn.close()
    return rows


def get_session_meta(session_id: int, user_id=None) -> Optional[dict]:
    """
    Fetch dashboard metadata for a session (title, KPIs, layout mode).

    When user_id is None, the row is fetched without an ownership check
    (used for shared/view-only dashboard links).

    Returns:
        dict with keys: dashboard_title, kpis_json, layout_mode
        None if the session is not found.
    """
    try:
        conn = _connect()
        c    = conn.cursor()
        if user_id is None:
            c.execute(
                _ph("SELECT dashboard_title, kpis_json, layout_mode "
                    "FROM sessions WHERE id=?"),
                (session_id,))
        else:
            c.execute(
                _ph("SELECT dashboard_title, kpis_json, layout_mode "
                    "FROM sessions WHERE id=? AND user_id=?"),
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


def get_session_charts(session_id: int, user_id=None) -> list:
    """
    Load and deserialise the charts stored in a saved session.

    Returns:
        list of tuples:
            (uid, title, fig, desc, auto_insights, chart_type, meta)

        where fig is a live Plotly Figure object deserialised from JSON.
        Tuples for charts that fail to deserialise are silently skipped.

    Note:
        This is a pure data function. Callers are responsible for writing
        the returned metadata into session_state if needed.
    """
    import plotly.io as pio
    conn = _connect()
    c    = conn.cursor()
    if user_id is None:
        c.execute(_ph("SELECT charts_json FROM sessions WHERE id=?"), (session_id,))
    else:
        c.execute(
            _ph("SELECT charts_json FROM sessions WHERE id=? AND user_id=?"),
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
            pass  # Skip damaged chart entries silently.
    return charts
