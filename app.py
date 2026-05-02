"""
app.py -- Lytrize application entry point.
==========================================

This is the ONLY file Streamlit runs directly:
    streamlit run app.py

Responsibilities:
  1. Configure the Streamlit page (title, icon, layout).
  2. Restore the logged-in user from a URL token on browser refresh.
  3. Restore an in-progress analysis draft from the database (fix #9).
  4. Guard every route -- unauthenticated users always land on "auth".
  5. Sync the current page name into the URL (?p=...) for browser history.
  6. Route to the correct page module based on st.session_state.page.

──────────────────────────────────────────────────────────────────────
ROUTING MAP  (st.session_state.page  →  function called)
──────────────────────────────────────────────────────────────────────
  "auth"      → modules/pages/auth.py      :: page_auth()
  "home"      → modules/pages/home.py      :: page_home()
  "upload"    → modules/pages/upload.py    :: page_upload()
  "analysis"  → modules/pages/analysis.py  :: page_analysis()
  "dashboard" → modules/pages/dashboard.py :: page_dashboard()
  "profile"   → modules/pages/auth.py      :: page_profile()

──────────────────────────────────────────────────────────────────────
URL QUERY PARAMETERS
──────────────────────────────────────────────────────────────────────
  ?t=<token>   -- persistent login token written by auth.py after sign-in
  ?p=<page>    -- current page slug; synced on every rerun
  ?sid=<int>   -- session ID to open in view-only dashboard mode
  ?nav=home    -- logo link signal to force-navigate to home

──────────────────────────────────────────────────────────────────────
CONTRIBUTING -- adding a new page
──────────────────────────────────────────────────────────────────────
  1. Create  modules/pages/my_page.py  with a  page_my_page()  function.
  2. Import it below.
  3. Add  elif p == "my_page": page_my_page()  in the router section.
  4. Navigate to it anywhere with:
       st.session_state.page = "my_page"; st.rerun()

Fixes implemented:
  #9  -- Page refresh restores the user's current page & in-progress
        analysis via the draft_sessions table.
  #10 -- Logo injected via CSS; auth page keeps text-only logo.
"""

import streamlit as st
import warnings
import json

warnings.filterwarnings("ignore")

# ── Page config MUST be the very first Streamlit call ─────────────────────────
st.set_page_config(
    page_title="Lytrize",
    page_icon="assets/lytrize.ico",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Internal imports (after set_page_config) ──────────────────────────────────
from modules.database import init_db, validate_token, get_draft
from modules.ui.css import inject_css
from modules.pages.auth      import page_auth, page_profile
from modules.pages.home      import page_home
from modules.pages.upload    import page_upload
from modules.pages.analysis  import page_analysis
from modules.pages.dashboard import page_dashboard


# ─────────────────────────────────────────────────────────────────────────────
# Draft restoration helper
# ─────────────────────────────────────────────────────────────────────────────

def _restore_draft(user_id: int) -> None:
    """
    Reload an in-progress analysis session from the database into session_state.

    Called once when a token-validated user has no page in session_state
    (fresh tab / browser refresh). Reads the draft_sessions row and
    repopulates session_state so the user resumes exactly where they left off.

    Args:
        user_id: The authenticated user's database row ID.

    Notes:
        - Individual chart deserialisation errors are silently skipped so a
          single corrupted chart never blocks the whole session from loading.
        - chart_meta_json keys are only written when not already present --
          existing session state always wins over the draft.
    """
    import plotly.io as pio

    draft = get_draft(user_id)
    if not draft:
        return  # No draft saved -- first-ever login or draft was cleared.

    # ── Restore the page the user had open before closing the tab ─────────────
    st.session_state.page = draft.get("page", "home")

    # ── Restore top-level dashboard metadata ──────────────────────────────────
    st.session_state.file_name       = draft.get("file_name", "")
    st.session_state.dashboard_title = draft.get("dashboard_title", "")
    st.session_state.layout_mode     = draft.get("layout_mode", "portrait")

    try:
        st.session_state.kpis = json.loads(draft.get("kpis_json", "[]"))
    except Exception:
        st.session_state.kpis = []

    # ── Restore edit-mode context (which saved session was being edited) ───────
    if draft.get("editing_session_id"):
        st.session_state.editing_session_id   = draft["editing_session_id"]
        st.session_state.editing_session_name = draft.get("editing_session_name", "")

    # ── Restore charts -- deserialise Plotly figures from JSON ─────────────────
    try:
        charts_raw = json.loads(draft.get("charts_json", "[]"))
        charts = []
        for item in charts_raw:
            uid           = item.get("uid", "")
            title         = item.get("title", "")
            fig_json      = item.get("fig_json", "")
            desc          = item.get("desc", "")
            auto_insights = item.get("auto_insights", [])
            chart_type    = item.get("chart_type", "")
            meta          = item.get("meta", {})
            try:
                fig = pio.from_json(fig_json)
                charts.append((uid, title, fig))
                # Store per-chart metadata under predictable session_state keys.
                # These keys are referenced throughout dashboard.py and analysis.py.
                st.session_state[f"desc_{uid}"]          = desc
                st.session_state[f"auto_insights_{uid}"] = auto_insights
                st.session_state[f"chart_type_{uid}"]    = chart_type
                st.session_state[f"chart_meta_{uid}"]    = meta
            except Exception:
                pass  # Skip damaged chart -- never block the whole session.
        if charts:
            st.session_state.charts = charts
    except Exception:
        pass

    # ── Restore per-chart meta keys (custom titles, axis labels, etc.) ─────────
    try:
        meta_map = json.loads(draft.get("chart_meta_json", "{}"))
        for k, v in meta_map.items():
            # Don't overwrite keys already restored from charts_json above.
            if k not in st.session_state:
                st.session_state[k] = v
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    """
    Bootstrap the app and route to the correct page on every Streamlit rerun.

    Execution order on each rerun:
        1. init_db()        -- idempotent table creation.
        2. inject_css()     -- global styles (Streamlit deduplicates injections).
        3. Token resolution -- validate ?t= param and restore authenticated user.
        4. Draft restore    -- reload the user's last analysis state from DB.
        5. Security guard   -- unauthenticated → force "auth" page.
        6. Home override    -- ?nav=home clears view/edit state → home.
        7. URL sync         -- keep ?p= and ?sid= accurate in the address bar.
        8. Router           -- call the appropriate page function.
    """
    # ── 1. Database -- create tables if they don't exist yet ───────────────────
    init_db()

    # ── 2. Global CSS injection ───────────────────────────────────────────────
    inject_css()

    # ── 3. Read URL parameters ────────────────────────────────────────────────
    url_token      = st.query_params.get("t", "")
    url_page       = st.query_params.get("p", "auth")
    url_session_id = st.query_params.get("sid", "")
    url_nav        = st.query_params.get("nav", "")

    # ── 4. Token → user resolution ────────────────────────────────────────────
    # Runs only when a token is present AND the user isn't already in session.
    # Covers: bookmark, shared link, and page refresh scenarios.
    if url_token and "user_id" not in st.session_state:
        restored = validate_token(url_token)
        if restored:
            st.session_state.user_id  = restored[0]
            st.session_state.username = restored[1]

            # Attempt to resume in-progress work from the draft table (fix #9).
            _restore_draft(restored[0])

            # Explicit URL navigation (e.g. a shared ?p=dashboard&sid=42 link)
            # takes priority over whatever page the draft stored.
            if url_page not in ("auth", "home") or url_session_id:
                st.session_state.page = url_page

            # Shared view-session link → open that session in read-only mode.
            if url_session_id:
                try:
                    st.session_state.view_session_id = int(url_session_id)
                    # Clear stale view cache so dashboard always loads fresh data.
                    st.session_state.pop("_view_charts",            None)
                    st.session_state.pop("_view_session_id_loaded", None)
                except Exception:
                    pass

    # ── 5. Security guard ─────────────────────────────────────────────────────
    if "user_id" not in st.session_state:
        # No authenticated user -- redirect to auth regardless of ?p=.
        st.session_state.page = "auth"
    elif "page" not in st.session_state:
        # Authenticated but no page set (no draft) → default to home.
        st.session_state.page = "home"

    # ── 6. Logo / home navigation override ───────────────────────────────────
    # The logo <a> link appends ?nav=home to force a clean home navigation,
    # bypassing any stale in-memory page that might linger in session_state.
    if "user_id" in st.session_state and url_nav == "home":
        for k in ["view_session_id", "_view_charts", "_vsid",
                  "_view_session_id_loaded", "dashboard_title", "kpis",
                  "layout_mode"]:
            st.session_state.pop(k, None)
        st.session_state.page = "home"
        st.query_params.pop("nav", None)

    # ── 7. URL sync -- keep address bar accurate for bookmarks / back button ───
    st.query_params["p"] = st.session_state.page
    if st.session_state.get("view_session_id"):
        st.query_params["sid"] = st.session_state.view_session_id
    else:
        st.query_params.pop("sid", None)

    # ── 8. Page router ────────────────────────────────────────────────────────
    p = st.session_state.page
    if   p == "auth":      page_auth()
    elif p == "home":      page_home()
    elif p == "upload":    page_upload()
    elif p == "analysis":  page_analysis()
    elif p == "dashboard": page_dashboard()
    elif p == "profile":   page_profile()


if __name__ == "__main__":
    main()
