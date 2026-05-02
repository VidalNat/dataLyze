"""
modules/pages/auth.py -- Login, registration, and profile management page.
==========================================================================

Exposes two entry-point functions called by app.py:
    page_auth()    -- sign-in / sign-up form for unauthenticated users
    page_profile() -- account settings, password change, account deletion

Authentication flow:
    1. User submits credentials → login_user() validates them.
    2. On success, create_token() issues a 7-day persistent token.
    3. The token is written to ?t= in the URL via st.query_params.
    4. Every subsequent page load validates the token via validate_token().
    5. Sign-out calls revoke_token() and clears session_state.

CONTRIBUTING -- to add a new profile setting:
    Add a new st.expander() block in page_profile() below the existing sections.
    Use the same confirm-before-action pattern as the account deletion block.
"""
"""
modules/pages/auth.py -- Login & Registration page.
Logo is text-only here per spec (#10).
"""

import streamlit as st
from modules.database import (
    login_user, register_user, validate_token, create_token,
    log_activity, delete_user_db,
)
from modules.ui.css import BRAND_NAME, inject_footer, logo_data_uri


def page_auth():
    token = st.query_params.get("t", "")
    if token and "user_id" not in st.session_state:
        restored = validate_token(token)
        if restored:
            st.session_state.user_id  = restored[0]
            st.session_state.username = restored[1]
            st.session_state.page     = "home"
            st.rerun()
        else:
            st.query_params.clear()

    tab = st.query_params.get("tab", "login")
    if "auth_tab" not in st.session_state:
        st.session_state.auth_tab = tab
    is_login = st.session_state.auth_tab == "login"

    _, col, _ = st.columns([1, 0.85, 1])
    with col:
        logo_src = logo_data_uri()
        icon_html = (
            f'<img src="{logo_src}" alt="{BRAND_NAME} logo" '
            'style="width:2.2rem;height:2.2rem;object-fit:contain;vertical-align:middle;margin-right:8px;">'
            if logo_src else
            '<span style="font-size:2rem;line-height:1;vertical-align:middle;margin-right:8px;">&#128202;</span>'
        )
        st.markdown(
            '<div style="text-align:center;padding-top:3rem;margin-bottom:2rem;">'
            f'<div style="display:inline-flex;align-items:center;justify-content:center;">{icon_html}'
            f'<span class="brand" style="font-size:2rem;">{BRAND_NAME}</span></div>'
            '<div style="font-size:0.88rem;margin-top:0.5rem;opacity:0.65;">'
            'Quick Analysis Platform</div>'
            '</div>',
            unsafe_allow_html=True)

        col_login, col_reg = st.columns(2)
        with col_login:
            if st.button("🔐 Login", use_container_width=True,
                         type="primary" if is_login else "secondary"):
                st.session_state.auth_tab = "login"; st.rerun()
        with col_reg:
            if st.button("✨ Register", use_container_width=True,
                         type="primary" if not is_login else "secondary"):
                st.session_state.auth_tab = "register"; st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)

        if is_login:
            username = st.text_input("Username", key="l_user")
            password = st.text_input("Password", type="password", key="l_pass")
            remember = st.checkbox("Stay signed in", value=True, key="remember_me")
            if st.button("Sign In →", use_container_width=True):
                user = login_user(username, password)
                if user:
                    st.session_state.user_id  = user[0]
                    st.session_state.username = user[1]
                    st.session_state.page     = "home"
                    log_activity(user[0], "login", f"user={username}")
                    if remember:
                        tok = create_token(user[0], user[1])
                        st.query_params["t"] = tok
                    else:
                        st.query_params.clear()
                    st.rerun()
                else:
                    st.error("Incorrect username or password.")
        else:
            ru  = st.text_input("Username",         key="r_u")
            re  = st.text_input("Email",            key="r_e")
            rp  = st.text_input("Password",         type="password", key="r_p")
            rp2 = st.text_input("Confirm Password", type="password", key="r_p2")
            if st.button("Create Account →", use_container_width=True):
                if rp != rp2:       st.error("Passwords don't match.")
                elif len(rp) < 6:   st.error("Password must be 6+ characters.")
                else:
                    ok, msg = register_user(ru, re, rp)
                    if ok:
                        st.success(msg)
                        log_activity(0, "register", f"new user={ru}")
                        st.session_state.auth_tab = "login"
                        st.rerun()
                    else:
                        st.error(msg)

    inject_footer()


def page_profile():
    """User profile page -- account info and danger-zone actions."""
    from modules.ui.css import render_logo
    render_logo()

    if st.button("← Back to Home"):
        st.session_state.page = "home"
        st.rerun()

    username = st.session_state.get("username", "")
    user_id  = st.session_state.get("user_id")

    st.markdown(f"## 👤 Profile -- {username}")
    st.markdown("---")

    # ── Danger Zone ───────────────────────────────────────────────────────────
    st.markdown(
        '<div style="border:1.5px solid #ef4444;border-radius:12px;padding:1rem 1.2rem;'
        'background:rgba(239,68,68,0.04);margin-top:1rem;">'
        '<p style="color:#ef4444;font-weight:700;font-size:0.95rem;margin:0 0 0.5rem 0;">'
        '⚠️ Danger Zone</p>'
        '<p style="font-size:0.84rem;opacity:0.8;margin:0;">'
        'Deleting your account is <strong>permanent and irreversible</strong>. '
        'All saved sessions, charts, KPIs, and your login will be erased immediately.'
        '</p></div>',
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)

    # Two-step confirmation: show confirm UI only after first button press
    if "confirm_delete_account" not in st.session_state:
        st.session_state.confirm_delete_account = False

    if not st.session_state.confirm_delete_account:
        if st.button("🗑️ Delete My Account", type="secondary"):
            st.session_state.confirm_delete_account = True
            st.rerun()
    else:
        st.warning(
            "Are you sure? This will permanently delete your account and **all saved sessions**. "
            "This cannot be undone."
        )
        col_yes, col_no, _ = st.columns([1, 1, 4])
        with col_yes:
            if st.button("✅ Yes, delete everything", type="primary",
                         use_container_width=True):
                ok = delete_user_db(user_id)
                if ok:
                    # Wipe session state fully and redirect to auth
                    for k in list(st.session_state.keys()):
                        del st.session_state[k]
                    st.query_params.clear()
                    st.session_state.page = "auth"
                    st.success("Your account has been deleted.")
                    st.rerun()
                else:
                    st.error("Something went wrong -- account could not be deleted. Try again.")
        with col_no:
            if st.button("✗ Cancel", use_container_width=True):
                st.session_state.confirm_delete_account = False
                st.rerun()

    inject_footer()
