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
        else:
            # Token is invalid or expired — clear it so the user isn't stuck
            # in a redirect loop between home and auth.
            st.query_params.clear()
            st.session_state.page = "auth"
            st.rerun()

    # ── Top navbar ────────────────────────────────────────────────────────────
    lc1, lc2, lc3, lc4 = st.columns([8, 1.1, 1.1, 1.1])
    with lc1:
        render_logo()
    with lc2:
        if st.button("🚀 New", use_container_width=True, help="Start new analysis"):
            log_activity(st.session_state.user_id, "new_analysis_started")
            for k in ["editing_session_id","editing_session_name","editing_file_name",
                      "df","charts","selected_analyses","dashboard_title","kpis",
                      "layout_mode","_view_charts","view_session_id"]:
                st.session_state.pop(k, None)
            st.session_state.page = "upload"; st.rerun()
    with lc3:
        if st.button("👤 Profile", use_container_width=True):
            st.session_state.page = "profile"; st.rerun()
    with lc4:
        if st.button("↩ Logout", use_container_width=True):
            tok = st.query_params.get("t", "")
            if tok: revoke_token(tok)
            log_activity(st.session_state.get("user_id", 0), "logout")
            st.query_params.clear(); st.session_state.clear()
            st.session_state.page = "auth"; st.rerun()

    st.markdown("<div style='height:.3rem'></div>", unsafe_allow_html=True)

    username = escape(str(st.session_state.username))
    sessions = get_user_sessions(st.session_state.user_id)

    # ── Welcome banner ────────────────────────────────────────────────────────
    total_charts = sum(1 for _ in sessions)  # quick proxy; no extra DB call
    unique_files  = len(set(s[2] for s in sessions)) if sessions else 0
    st.markdown(f"""
    <div class="welcome-banner">
        <div style="display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:1rem;">
          <div>
            <div style="font-size:.72rem;opacity:.75;font-weight:700;letter-spacing:.12em;
                        text-transform:uppercase;margin-bottom:.45rem;">WORKSPACE</div>
            <div style="font-size:1.9rem;font-weight:800;font-family:'Sora',sans-serif;
                        margin-bottom:.35rem;letter-spacing:-.03em;">
                Welcome back, {username} 👋
            </div>
            <div style="font-size:.9rem;opacity:.85;line-height:1.65;max-width:480px;">
                Your analysis workspace is ready — upload a new dataset or continue where you left off.
            </div>
          </div>
          <div style="display:flex;gap:.6rem;flex-wrap:wrap;align-items:center;">
            <span class="pill">📁 {len(sessions)} session{'s' if len(sessions)!=1 else ''}</span>
            <span class="pill">🗂️ {unique_files} dataset{'s' if unique_files!=1 else ''}</span>
            <span class="pill">🔬 {len(ANALYSIS_OPTIONS)} analysis types</span>
          </div>
        </div>
    </div>""", unsafe_allow_html=True)

    # ── Sessions list ─────────────────────────────────────────────────────────
    st.markdown('<div class="sec-label">📁 Saved Sessions</div>', unsafe_allow_html=True)

    if not sessions:
        st.markdown("""
        <div class="glass-card" style="padding:2.5rem;text-align:center;">
          <div style="font-size:2.5rem;margin-bottom:.8rem;">📂</div>
          <div style="font-weight:700;font-size:1rem;margin-bottom:.4rem;">No sessions yet</div>
          <div style="font-size:.85rem;opacity:.6;">Click <strong>🚀 New</strong> in the top bar to start your first analysis.</div>
        </div>""", unsafe_allow_html=True)
    else:
        for s in sessions[:12]:
            sid, sname, fname, rows, cols, atypes, created = s
            safe_sname   = escape(str(sname))
            safe_fname   = escape(str(fname or ""))
            safe_created = str(created or "")[:16]

            with st.container():
                sa, sb, sc, sd, se = st.columns([4, 1, 1, 1, 1])
                with sa:
                    st.markdown(
                        f'<div class="sess-card glass-card">'
                        f'  <b>{safe_sname}</b><br>'
                        f'  <small>📄 {safe_fname} &nbsp;·&nbsp; {rows:,}×{cols} &nbsp;·&nbsp; 🕐 {safe_created}</small>'
                        f'</div>',
                        unsafe_allow_html=True)
                with sb:
                    if st.button("👁 View", key=f"v_{sid}", use_container_width=True):
                        st.session_state.view_session_id   = sid
                        st.session_state.view_session_name = sname
                        for k in ("_view_charts","_view_session_id_loaded",
                                  "dashboard_title","kpis","layout_mode"):
                            st.session_state.pop(k, None)
                        log_activity(st.session_state.user_id,"session_viewed",f"id={sid}",sid)
                        st.session_state.page = "dashboard"; st.rerun()
                with sc:
                    if st.button("✏️ Edit", key=f"edit_btn_{sid}", use_container_width=True):
                        saved = get_session_charts(sid, st.session_state.user_id)
                        st.session_state.charts = [(uid,title,fig) for uid,title,fig,*_ in saved]
                        for uid,title,fig,desc,auto,ctype,meta in saved:
                            st.session_state[f"desc_{uid}"]          = desc
                            st.session_state[f"auto_insights_{uid}"] = auto
                            st.session_state[f"chart_type_{uid}"]    = ctype
                            st.session_state[f"chart_meta_{uid}"]    = meta
                        st.session_state.selected_analyses    = []
                        st.session_state.editing_session_id   = sid
                        st.session_state.editing_session_name = sname
                        st.session_state.editing_file_name    = fname
                        st.session_state.setdefault("file_name", fname)
                        for k in ("view_session_id","_edit_notes_loaded",
                                  "_analysis_notes_loaded","_notes_shadow"):
                            st.session_state.pop(k, None)
                        log_activity(st.session_state.user_id,"session_edit_started",f"id={sid}",sid)
                        st.session_state.page = "analysis"; st.rerun()
                with sd:
                    if st.button("🔤", key=f"rename_btn_{sid}",
                                 help="Rename", use_container_width=True):
                        st.session_state[f"renaming_{sid}"] = True
                with se:
                    if st.button("🗑️", key=f"del_btn_{sid}",
                                 help="Delete", use_container_width=True):
                        st.session_state[f"confirm_del_{sid}"] = True

            if st.session_state.get(f"renaming_{sid}"):
                with st.container():
                    new_name = st.text_input("New name:", value=sname, key=f"new_name_{sid}",
                                             label_visibility="collapsed")
                    r1, r2, _ = st.columns([1, 1, 5])
                    with r1:
                        if st.button("✅ Save", key=f"save_rename_{sid}", use_container_width=True):
                            rename_session_db(sid, new_name, st.session_state.user_id)
                            log_activity(st.session_state.user_id,"session_renamed",
                                         f"id={sid} new='{new_name}'",sid)
                            st.session_state.pop(f"renaming_{sid}", None)
                            st.toast(f"Renamed to '{new_name}'", icon="✏️")
                            st.rerun()
                    with r2:
                        if st.button("✕ Cancel", key=f"cancel_rename_{sid}", use_container_width=True):
                            st.session_state.pop(f"renaming_{sid}", None); st.rerun()

            if st.session_state.get(f"confirm_del_{sid}"):
                with st.container():
                    st.markdown(
                        f'<div class="danger-box" style="margin:.3rem 0;">'
                        f'⚠️ Delete <strong>{safe_sname}</strong>? This cannot be undone.</div>',
                        unsafe_allow_html=True)
                    d1, d2, _ = st.columns([1, 1, 5])
                    with d1:
                        if st.button("🗑️ Delete", key=f"confirm_yes_{sid}",
                                     use_container_width=True):
                            delete_session_db(sid, st.session_state.user_id)
                            st.session_state.pop(f"confirm_del_{sid}", None)
                            st.toast("Session deleted.", icon="🗑️"); st.rerun()
                    with d2:
                        if st.button("✕ Keep", key=f"confirm_no_{sid}",
                                     use_container_width=True):
                            st.session_state.pop(f"confirm_del_{sid}", None); st.rerun()

    inject_footer()
