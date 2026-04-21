"""
DataLyze — Intelligent Data Analysis Platform
v2.0.0 — Modular architecture

━━━ POSTGRESQL SWITCH GUIDE ━━━
To use PostgreSQL instead of SQLite:
  1. pip install psycopg2-binary
  2. Set env var: DATALYZE_DB_URL=postgresql://user:password@localhost:5432/datalyze
  3. In modules/database.py, replace _connect() with:
       import psycopg2, os
       def _connect():
           return psycopg2.connect(os.environ["DATALYZE_DB_URL"])
  4. Replace all ? placeholders with %s in that file.
  No other files need changes.

━━━ ADDING A NEW ANALYSIS TYPE ━━━
  1. Create modules/analysis/my_feature.py
       def run_my_feature(df, **kwargs) -> list[tuple[str, Figure]]: ...
  2. In modules/analysis/__init__.py:
       - Import run_my_feature
       - Add entry to ANALYSIS_OPTIONS list
       - Add entry to _RUNNERS dict
       - Add axis config to _axis_selector() if needed
       - Add to _NO_FORM set if your function uses st.button internally
  3. Done — it auto-appears on the analysis page.
"""

import streamlit as st
import warnings
warnings.filterwarnings("ignore")

st.set_page_config(
    page_title="DataLyze",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from modules.database import init_db, validate_token
from modules.ui.css import inject_css
from modules.pages.auth      import page_auth
from modules.pages.home      import page_home
from modules.pages.upload    import page_upload
from modules.pages.analysis  import page_analysis
from modules.pages.dashboard import page_dashboard


def main():
    init_db()
    inject_css()

    # Restore session from URL token on any page load (handles browser refresh)
    token = st.query_params.get("t", "")
    if token and "user_id" not in st.session_state:
        restored = validate_token(token)
        if restored:
            st.session_state.user_id  = restored[0]
            st.session_state.username = restored[1]
            if "page" not in st.session_state:
                st.session_state.page = "home"

    if "page" not in st.session_state:
        st.session_state.page = "auth"
    if st.session_state.page != "auth" and "user_id" not in st.session_state:
        st.session_state.page = "auth"

    p = st.session_state.page
    if   p == "auth":      page_auth()
    elif p == "home":      page_home()
    elif p == "upload":    page_upload()
    elif p == "analysis":  page_analysis()
    elif p == "dashboard": page_dashboard()


if __name__ == "__main__":
    main()
