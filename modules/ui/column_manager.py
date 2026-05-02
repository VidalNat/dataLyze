"""
modules/ui/column_manager.py -- Dashboard column-layout helpers.
================================================================

Provides layout utility functions used by the dashboard page to arrange
chart cards in portrait (2-column) or landscape (3-column) grids.

Functions:
    get_column_layout(layout_mode)  -- returns the Streamlit column spec list
    render_chart_grid(charts, ...)  -- renders all chart cards into the grid

CONTRIBUTING -- to add a new layout mode:
    1. Add an entry to the layout_mode selectbox in dashboard.py.
    2. Add a matching branch in get_column_layout() returning a column spec.
       Streamlit column specs are lists of relative widths, e.g. [1, 1, 1].
"""
"""
modules/ui/column_manager.py
Column add / remove UI shown on the upload page.
"""

import streamlit as st
import numpy as np
import pandas as pd
from modules.database import log_activity


def show_column_manager(df):
    st.markdown("---")
    st.markdown("## 🛠️ Column Manager")
    tab_add, tab_remove = st.tabs(["➕ Add Column", "🗑️ Remove Column"])

    with tab_add:
        num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        a1, a2 = st.columns(2)
        with a1: new_col_name = st.text_input("New column name", key="new_col_name")
        with a2:
            calc_type = st.selectbox("Calculation type", [
                "Custom formula (use col names)", "Column × Column", "Column ÷ Column",
                "Column + Column", "Column − Column", "Extract Date/Time Part"
            ], key="calc_type")

        formula_str = date_col = part_to_extract = None

        if calc_type == "Custom formula (use col names)":
            formula_str = st.text_input("Formula", key="custom_formula", placeholder="e.g. Sales / Units")
        elif calc_type in ("Column × Column", "Column ÷ Column", "Column + Column", "Column − Column"):
            op_map = {"Column × Column":"*","Column ÷ Column":"/","Column + Column":"+","Column − Column":"-"}
            op = op_map[calc_type]
            b1, b2 = st.columns(2)
            with b1: col_a = st.selectbox("First", num_cols, key="col_a")
            with b2: col_b = st.selectbox("Second", num_cols, key="col_b")
            formula_str = f"`{col_a}` {op} `{col_b}`"
        elif calc_type == "Extract Date/Time Part":
            b1, b2 = st.columns(2)
            with b1: date_col = st.selectbox("Source Date Column", df.columns, key="date_col")
            with b2: part_to_extract = st.selectbox("Part to Extract",
                ["Year","Month (Number)","Month Name","Day","Weekday Name","Hour"], key="date_part_ext")
            formula_str = "date_extraction_placeholder"

        if st.button("➕ Add Column", key="btn_add_col"):
            if not new_col_name.strip() or not formula_str:
                st.error("Fill all fields.")
            else:
                try:
                    if calc_type == "Extract Date/Time Part":
                        temp_dates = pd.to_datetime(df[date_col], errors='coerce')
                        mapping = {
                            "Year": temp_dates.dt.year,
                            "Month (Number)": temp_dates.dt.month,
                            "Month Name": temp_dates.dt.month_name(),
                            "Day": temp_dates.dt.day,
                            "Weekday Name": temp_dates.dt.day_name(),
                            "Hour": temp_dates.dt.hour,
                        }
                        df[new_col_name.strip()] = mapping[part_to_extract]
                    else:
                        df[new_col_name.strip()] = df.eval(formula_str)
                    st.session_state.df = df
                    st.success(f"✅ Added {new_col_name.strip()}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    with tab_remove:
        col_to_del = st.selectbox("Select column to remove", df.columns.tolist(), key="col_to_del")
        confirm = st.checkbox(f"Confirm removal of **{col_to_del}**", key="confirm_del")
        if st.button("🗑️ Remove", key="btn_del_col", disabled=not confirm):
            df = df.drop(columns=[col_to_del])
            st.session_state.df = df
            for k in ["num_cols", "cat_cols"]:
                if k in st.session_state:
                    st.session_state[k] = [c for c in st.session_state[k] if c != col_to_del]
            st.success(f"✅ Removed {col_to_del}")
            st.rerun()

    return st.session_state.df
