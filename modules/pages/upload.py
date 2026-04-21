"""modules/pages/upload.py — File upload & pre-processing page."""

import streamlit as st
import pandas as pd
from modules.ui.column_manager import show_column_manager
from modules.ui.column_tools import show_dtype_transformer, show_column_classifier
from modules.ui.css import inject_footer


def page_upload():
    if st.button("← Home"):
        st.session_state.page = "home"; st.rerun()

    st.markdown("## 📂 Upload Dataset")
    uploaded = st.file_uploader("CSV or Excel", type=["csv", "xlsx", "xls"])

    if uploaded:
        if "df" not in st.session_state or st.session_state.get("file_name") != uploaded.name:
            with st.spinner("Reading file…"):
                df = (pd.read_csv(uploaded) if uploaded.name.endswith(".csv")
                      else pd.read_excel(uploaded))
            st.session_state.df        = df
            st.session_state.file_name = uploaded.name
        else:
            df = st.session_state.df

        st.success(f"✅ Loaded {uploaded.name} ({df.shape[0]:,} rows × {df.shape[1]} columns)")
        st.dataframe(df.head(), use_container_width=True)

        df = show_column_manager(df)
        df = show_dtype_transformer(df)
        show_column_classifier(df)

        with st.expander("📖 Describe Your Columns (optional — improves auto-insights)", expanded=False):
            st.markdown(
                "Describe what each column means. These descriptions appear in chart insights "
                "to give context-aware observations. Leave blank to skip."
            )
            col_descs = st.session_state.get("col_descriptions", {})
            for col in df.columns:
                col_descs[col] = st.text_input(
                    f"`{col}`", value=col_descs.get(col, ""),
                    key=f"coldesc_{col}",
                    placeholder="e.g. 'Total revenue in USD per transaction'")
            if st.button("💾 Save Column Descriptions", key="save_col_descs"):
                st.session_state.col_descriptions = col_descs
                st.success("✅ Column descriptions saved — they'll appear in chart insights.")

    inject_footer()
