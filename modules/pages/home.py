"""
modules/pages/home.py -- Home / dashboard overview page.
=========================================================

Shown after login. Displays:
  - Welcome banner with the user's name
  - KPI cards: saved sessions count, total charts, available analysis types
  - Grid of saved session cards with rename / delete / open / resume actions
  - Footer

Bug fix applied:
    The "Available analysis" KPI card previously showed the hardcoded number 9.
    It now uses len(ANALYSIS_OPTIONS) so it stays accurate automatically.

CONTRIBUTING -- to add a new KPI card to this page:
    Add an HTML string to the `kpi_row` list in page_home() using the
    .kpi-card / .kpi-icon / .kpi-val / .kpi-lbl CSS classes from ui/css.py.
"""

import streamlit as st
from html import escape
from modules.database import (
    validate_token, revoke_token, log_activity,
    get_user_sessions, get_session_charts,
    rename_session_db, delete_session_db,
)
from modules.ui.css import inject_footer, render_logo
from modules.analysis import ANALYSIS_OPTIONS


def page_home():
    token = st.query_params.get("t", "")
    if token and "user_id" not in st.session_state:
        restored = validate_token(token)
        if restored:
            st.session_state.user_id  = restored[0]
            st.session_state.username = restored[1]
            st.session_state.page     = "home"
            st.rerun()

    # Logo + logout row
    lc1, lc2, lc3 = st.columns([13, 1, 1])
    with lc1:
        render_logo()
    with lc2:
        if st.button("👤 Profile"):
            st.session_state.page = "profile"
            st.rerun()
    with lc3:
        if st.button("📤 Logout"):
            tok = st.query_params.get("t", "")
            if tok: revoke_token(tok)
            log_activity(st.session_state.get("user_id", 0), "logout")
            st.query_params.clear()
            st.session_state.clear()
            st.session_state.page = "auth"
            st.rerun()

    st.markdown("---")

    username = escape(str(st.session_state.username))
    st.markdown(f"""
    <div class="welcome-banner" style="text-align: center; padding: 1.2rem 1.5rem;">
        <div style="font-size:0.75rem;opacity:0.75;font-weight:600;letter-spacing:0.1em;
                    text-transform:uppercase;margin-bottom:0.4rem;">DASHBOARD OVERVIEW</div>
        <div style="font-size:2.1rem;font-weight:800;font-family:'Sora',sans-serif;
                    margin-bottom:0.4rem;letter-spacing:-0.03em;">
            Welcome back, {username} 👋
        </div>
        <div style="font-size:0.95rem;opacity:0.88;line-height:1.6;">
            Your data intelligence workspace is ready. Upload a dataset or pick up where you left off.
        </div>
    </div>""", unsafe_allow_html=True)

    sessions = get_user_sessions(st.session_state.user_id)
    m1, m2, m3 = st.columns(3)
    with m1:
        st.markdown(
            f'<div class="kpi-card"><div class="kpi-icon">📁</div>'
            f'<div class="kpi-val">{len(sessions)}</div>'
            f'<div class="kpi-lbl">Saved Sessions</div></div>',
            unsafe_allow_html=True)
    with m2:
        unique_files = len(set(s[2] for s in sessions)) if sessions else 0
        st.markdown(
            f'<div class="kpi-card"><div class="kpi-icon">🗂️</div>'
            f'<div class="kpi-val">{unique_files}</div>'
            f'<div class="kpi-lbl">Datasets Analysed</div></div>',
            unsafe_allow_html=True)
    with m3:
        st.markdown(
            '<div class="kpi-card"><div class="kpi-icon">🔬</div>'
            '<div class="kpi-val">' + str(len(ANALYSIS_OPTIONS)) + '</div>'
            '<div class="kpi-lbl">Available analysis</div></div>',
            unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🚀 Start New Analysis", use_container_width=False):
        log_activity(st.session_state.user_id, "new_analysis_started")
        # Clear any leftover draft / editing state for a fresh start
        for k in ["editing_session_id", "editing_session_name", "editing_file_name",
                  "df", "charts", "selected_analyses", "dashboard_title", "kpis",
                  "layout_mode", "_view_charts", "view_session_id"]:
            st.session_state.pop(k, None)
        st.session_state.page = "upload"; st.rerun()

    st.markdown('<div class="sec-label">📁 Previous Sessions</div>', unsafe_allow_html=True)

    if not sessions:
        st.info("No saved sessions yet. Start your first analysis above!")
    else:
        for s in sessions[:8]:
            sid, sname, fname, rows, cols, atypes, created = s
            safe_sname = escape(str(sname))
            safe_fname = escape(str(fname or ""))
            safe_created = escape(str(created or ""))
            sa, sb, sc, sd, se = st.columns([3, 1, 1, 1, 1])
            with sa:
                st.markdown(
                    f'<div class="sess-card"><b>{safe_sname}</b><br>'
                    f'<small>{safe_fname} · {rows}×{cols} · {safe_created[:16]}</small></div>',
                    unsafe_allow_html=True)
            with sb:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("View", key=f"v_{sid}"):
                    st.session_state.view_session_id   = sid
                    st.session_state.view_session_name = sname
                    # Clear stale _view_charts so dashboard reloads fresh
                    st.session_state.pop("_view_charts",            None)
                    st.session_state.pop("_view_session_id_loaded", None)
                    st.session_state.pop("dashboard_title",         None)
                    st.session_state.pop("kpis",                    None)
                    st.session_state.pop("layout_mode",             None)
                    log_activity(st.session_state.user_id, "session_viewed",
                                 f"session_id={sid}", sid)
                    st.session_state.page = "dashboard"; st.rerun()
            with sc:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("✏️ Edit", key=f"edit_btn_{sid}"):
                    saved = get_session_charts(sid, st.session_state.user_id)
                    # saved is list of 7-tuples: (uid, title, fig, desc, auto, ctype, meta)
                    st.session_state.charts = [(uid, title, fig) for uid, title, fig, *_ in saved]
                    for uid, title, fig, desc, auto, ctype, meta in saved:
                        st.session_state[f"desc_{uid}"]          = desc
                        st.session_state[f"auto_insights_{uid}"] = auto
                        st.session_state[f"chart_type_{uid}"]    = ctype
                        st.session_state[f"chart_meta_{uid}"]    = meta
                    st.session_state.selected_analyses    = []
                    st.session_state.editing_session_id   = sid
                    st.session_state.editing_session_name = sname
                    st.session_state.editing_file_name    = fname
                    st.session_state.setdefault("file_name", fname)
                    # Clear any old view state
                    st.session_state.pop("view_session_id", None)
                    # Always clear this flag so dashboard re-loads notes fresh
                    # for the newly opened session (guards against stale flag
                    # from a previously edited session in the same browser tab).
                    st.session_state.pop("_edit_notes_loaded",      None)
                    st.session_state.pop("_analysis_notes_loaded",  None)
                    st.session_state.pop("_notes_shadow",           None)
                    log_activity(st.session_state.user_id, "session_edit_started",
                                 f"session_id={sid}", sid)
                    st.session_state.page = "analysis"; st.rerun()
            with sd:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("🔤", key=f"rename_btn_{sid}", help="Rename this session"):
                    st.session_state[f"renaming_{sid}"] = True
            with se:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("🗑️", key=f"del_btn_{sid}", help="Delete this session"):
                    st.session_state[f"confirm_del_{sid}"] = True

            if st.session_state.get(f"renaming_{sid}"):
                new_name = st.text_input("New session name", value=sname, key=f"new_name_{sid}")
                r1, r2 = st.columns(2)
                with r1:
                    if st.button("✅ Save", key=f"save_rename_{sid}"):
                        rename_session_db(sid, new_name, st.session_state.user_id)
                        log_activity(st.session_state.user_id, "session_renamed",
                                     f"id={sid} new='{new_name}'", sid)
                        st.session_state.pop(f"renaming_{sid}", None)
                        st.success(f"Renamed to '{new_name}'")
                        st.rerun()
                with r2:
                    if st.button("Cancel", key=f"cancel_rename_{sid}"):
                        st.session_state.pop(f"renaming_{sid}", None); st.rerun()

            if st.session_state.get(f"confirm_del_{sid}"):
                st.warning(f"⚠️ Delete **{sname}**? This cannot be undone.")
                d1, d2 = st.columns(2)
                with d1:
                    if st.button("🗑️ Yes, delete", key=f"confirm_yes_{sid}"):
                        delete_session_db(sid, st.session_state.user_id)
                        st.session_state.pop(f"confirm_del_{sid}", None)
                        st.success("Session deleted."); st.rerun()
                with d2:
                    if st.button("Cancel", key=f"confirm_no_{sid}"):
                        st.session_state.pop(f"confirm_del_{sid}", None); st.rerun()

    inject_footer()
