"""modules/pages/auth.py — Login & Registration page."""

import streamlit as st
from modules.database import login_user, register_user, validate_token, create_token, log_activity
from modules.ui.css import inject_footer


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
        st.markdown(
            '<div style="text-align:center;padding-top:3rem;margin-bottom:2rem;">'
            '<div class="brand" style="font-size:2rem;">📊 DataLyze</div>'
            '<div style="font-size:0.88rem;margin-top:0.5rem;opacity:0.65;">'
            'Intelligent Data Analysis Platform</div>'
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
            ru  = st.text_input("Username", key="r_u")
            re  = st.text_input("Email",    key="r_e")
            rp  = st.text_input("Password", type="password", key="r_p")
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
