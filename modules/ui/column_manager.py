"""
modules/ui/column_manager.py -- Column add / remove UI shown on the upload page.
"""
import streamlit as st
import numpy as np
import pandas as pd

def show_column_manager(df):
    st.markdown("---")
    st.markdown("## 🛠️ Column Manager")
    
    tab_add, tab_remove = st.tabs(["➕ Add Column", "🗑️ Remove Column"])
    
    with tab_add:
        num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        all_cols = df.columns.tolist()
        
        a1, a2 = st.columns(2)
        with a1: new_col_name = st.text_input("New column name", key="new_col_name")
        with a2:
            calc_type = st.selectbox("Calculation type", [
                "Custom formula (use col names)", "Column × Column", "Column ÷ Column",
                "Column + Column", "Column − Column", "Extract Date/Time Part",
                "String Concatenation", "String Operations", "Conditional Column",
                "Binning/Categorization", "Mathematical Transform", "Aggregation (GroupBy)"
            ], key="calc_type")

        formula_str = date_col = part_to_extract = None

        # ── EXTRACT DATE/TIME PART (ROBUST 12/24-HOUR FIX) ─────────────────
        if calc_type == "Extract Date/Time Part":
            b1, b2 = st.columns(2)
            with b1: date_col = st.selectbox("Source Date/Time Column", df.columns, key="date_col")
            with b2: part_to_extract = st.selectbox("Part to Extract",
                [
                    "Year", "Month (Number)", "Month Name", "Day", 
                    "Weekday Name", "Hour (24H)", "Hour (12H with AM/PM)",
                    "Hour (12H numeric)", "Minute", "Second",
                    "Quarter", "Week Number", "Day of Year",
                    "Is Weekend", "Days from today", "Time (HH:MM:SS)"
                ], key="date_part_ext")
            formula_str = "date_extraction_placeholder"

        # ... [rest of String Concatenation, String Operations, etc. remain same] ...

        if st.button("➕ Add Column", key="btn_add_col"):
            if not new_col_name.strip() or not formula_str:
                st.error("Fill all fields.")
            else:
                try:
                    with st.spinner("Processing..."):
                        if calc_type == "Extract Date/Time Part":
                            temp_dates = pd.to_datetime(df[date_col], errors='coerce')
                            
                            # Robust extraction with proper 12-hour handling
                            mapping = {
                                "Year": temp_dates.dt.year,
                                "Month (Number)": temp_dates.dt.month,
                                "Month Name": temp_dates.dt.month_name(),
                                "Day": temp_dates.dt.day,
                                "Weekday Name": temp_dates.dt.day_name(),
                                
                                # FIXED: Hour extraction options
                                "Hour (24H)": temp_dates.dt.hour,  # 0-23
                                
                                "Hour (12H with AM/PM)": temp_dates.dt.strftime('%I %p'),  # 12 AM, 01 AM... 11 AM, 12 PM, 01 PM... 11 PM
                                
                                "Hour (12H numeric)": temp_dates.dt.hour.apply(
                                    lambda h: 12 if h == 0 else (h if h <= 12 else h - 12)
                                ),  # 12, 1, 2... 11, 12, 1... 11
                                
                                "Minute": temp_dates.dt.minute,
                                "Second": temp_dates.dt.second,
                                
                                "Quarter": temp_dates.dt.quarter,
                                "Week Number": temp_dates.dt.isocalendar().week,
                                "Day of Year": temp_dates.dt.dayofyear,
                                "Is Weekend": temp_dates.dt.dayofweek >= 5,
                                "Days from today": (temp_dates - pd.Timestamp.today()).dt.days,
                                
                                # Time string
                                "Time (HH:MM:SS)": temp_dates.dt.strftime('%H:%M:%S')
                            }
                            
                            df[new_col_name.strip()] = mapping[part_to_extract]
                        else:
                            df[new_col_name.strip()] = df.eval(formula_str)
                    
                    st.session_state.df = df
                    st.toast(f"Added column '{new_col_name.strip()}'", icon="➕")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

        # ... [Remove Column tab remains same] ...

    return st.session_state.df