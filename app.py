"""
app.py — Lytrize entry point.
Fixes:
  #9 — Page refresh restores the user's current page & in-progress analysis
       via draft_sessions table (not just the URL token).
  #10 — Logo injected in css; auth page keeps text-only logo.
"""

import streamlit as st
import warnings
import json
warnings.filterwarnings("ignore")

st.set_page_config(
    page_title="Lytrize",
    page_icon="assets/lytrize.ico",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from modules.database import init_db, validate_token, get_draft
from modules.ui.css import inject_css
from modules.pages.auth      import page_auth
from modules.pages.home      import page_home
from modules.pages.upload    import page_upload
from modules.pages.analysis  import page_analysis
from modules.pages.dashboard import page_dashboard


def _restore_draft(user_id):
    """
    Restore an in-progress analysis session from the database draft.
    Called once when a token-validated user has no page in session_state.
    """
    import plotly.io as pio
    draft = get_draft(user_id)
    if not draft:
        return

    # Restore page
    page = draft.get("page", "home")
    st.session_state.page = page

    # Restore dashboard-level meta
    st.session_state.file_name       = draft.get("file_name", "")
    st.session_state.dashboard_title = draft.get("dashboard_title", "")
    st.session_state.layout_mode     = draft.get("layout_mode", "portrait")

    try:
        st.session_state.kpis = json.loads(draft.get("kpis_json", "[]"))
    except Exception:
        st.session_state.kpis = []

    # Restore editing context
    if draft.get("editing_session_id"):
        st.session_state.editing_session_id   = draft["editing_session_id"]
        st.session_state.editing_session_name = draft.get("editing_session_name", "")

    # Restore charts
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
                st.session_state[f"desc_{uid}"]          = desc
                st.session_state[f"auto_insights_{uid}"] = auto_insights
                st.session_state[f"chart_type_{uid}"]    = chart_type
                st.session_state[f"chart_meta_{uid}"]    = meta
            except Exception:
                pass
        if charts:
            st.session_state.charts = charts
    except Exception:
        pass

    # Restore per-chart meta keys
    try:
        meta_map = json.loads(draft.get("chart_meta_json", "{}"))
        for k, v in meta_map.items():
            if k not in st.session_state:
                st.session_state[k] = v
    except Exception:
        pass


def main():
    init_db()
    inject_css()

    url_token      = st.query_params.get("t", "")
    url_page       = st.query_params.get("p", "auth")
    url_session_id = st.query_params.get("sid", "")
    url_nav        = st.query_params.get("nav", "")

    # ── Restore user from token ───────────────────────────────────────────────
    if url_token and "user_id" not in st.session_state:
        restored = validate_token(url_token)
        if restored:
            st.session_state.user_id  = restored[0]
            st.session_state.username = restored[1]

            # Try to restore in-progress draft (page refresh recovery #9)
            _restore_draft(restored[0])

            # URL page takes priority for explicit navigation (view/sid links)
            if url_page not in ("auth", "home") or url_session_id:
                st.session_state.page = url_page

            # If they were viewing a saved session via URL
            if url_session_id:
                try:
                    st.session_state.view_session_id = int(url_session_id)
                    st.session_state.pop("_view_charts",            None)
                    st.session_state.pop("_view_session_id_loaded", None)
                except Exception:
                    pass

    # ── Security guard ────────────────────────────────────────────────────────
    if "user_id" not in st.session_state:
        st.session_state.page = "auth"
    elif "page" not in st.session_state:
        st.session_state.page = "home"

    # Explicit logo/home navigation must win over stale in-memory page state.
    if "user_id" in st.session_state and url_nav == "home":
        for k in ["view_session_id", "_view_charts", "_vsid",
                  "_view_session_id_loaded", "dashboard_title", "kpis",
                  "layout_mode"]:
            st.session_state.pop(k, None)
        st.session_state.page = "home"
        st.query_params.pop("nav", None)

    # ── Sync URL ──────────────────────────────────────────────────────────────
    st.query_params["p"] = st.session_state.page
    if st.session_state.get("view_session_id"):
        st.query_params["sid"] = st.session_state.view_session_id
    else:
        st.query_params.pop("sid", None)

    # ── Route ─────────────────────────────────────────────────────────────────
    p = st.session_state.page
    if   p == "auth":      page_auth()
    elif p == "home":      page_home()
    elif p == "upload":    page_upload()
    elif p == "analysis":  page_analysis()
    elif p == "dashboard": page_dashboard()


if __name__ == "__main__":
    main()
