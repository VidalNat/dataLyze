"""
modules/ui/column_tools.py
Data-type transformer and column classifier widgets shown on the upload page.
"""

import streamlit as st
import numpy as np
import pandas as pd
import datetime


def show_dtype_transformer(df):
    st.markdown("---")
    st.markdown("## 🔍 Data Type Inspector & Transformer")

    dtype_df = pd.DataFrame({
        "Column": df.columns,
        "Current Dtype": df.dtypes.astype(str),
        "Sample Value": [str(df[col].iloc[0]) if len(df) > 0 else "" for col in df.columns]
    }).reset_index(drop=True)
    st.dataframe(dtype_df, use_container_width=True, hide_index=False)

    st.markdown("### 🛠️ Transform Column Types")
    col_to_convert = st.selectbox("Select column to transform", df.columns, key="dtype_col")
    current_dtype = str(df[col_to_convert].dtype)

    target_options = ["object","string","int64","float64","bool","category",
                      "datetime64[ns]","date","time","timedelta64[ns]"]

    default_idx = target_options.index("object")
    if "int" in current_dtype:      default_idx = target_options.index("int64")
    elif "float" in current_dtype:  default_idx = target_options.index("float64")
    elif "datetime" in current_dtype: default_idx = target_options.index("datetime64[ns]")
    elif "bool" in current_dtype:   default_idx = target_options.index("bool")

    new_dtype = st.selectbox(
        f"Convert '{col_to_convert}' from `{current_dtype}` to:",
        options=target_options, index=default_idx,
        key=f"dtype_target_{col_to_convert}")

    if st.button("🔄 Apply Transformation", key=f"apply_dtype_{col_to_convert}"):
        try:
            if new_dtype == "datetime64[ns]":
                converted = pd.to_datetime(df[col_to_convert], errors='coerce')
            elif new_dtype == "date":
                converted = pd.to_datetime(df[col_to_convert], errors='coerce').dt.date
            elif new_dtype == "time":
                # Handle pure time strings like "07:06:11" which pd.to_datetime
                # can't parse alone — prepend a dummy date.
                def _to_time(val):
                    if pd.isna(val) or val is None:
                        return None
                    if isinstance(val, datetime.time):
                        return val
                    s = str(val).strip()
                    try:
                        return pd.to_datetime("1970-01-01 " + s).time()
                    except Exception:
                        try:
                            return pd.to_datetime(s).time()
                        except Exception:
                            return None
                converted = df[col_to_convert].apply(_to_time)
            elif new_dtype == "timedelta64[ns]":
                # pd.to_timedelta handles "HH:MM:SS" strings natively.
                # If values are Python datetime.time objects, convert via str first.
                def _to_td(val):
                    if pd.isna(val) or val is None:
                        return pd.NaT
                    if isinstance(val, datetime.time):
                        return pd.Timedelta(hours=val.hour, minutes=val.minute,
                                            seconds=val.second,
                                            microseconds=val.microsecond)
                    try:
                        return pd.to_timedelta(str(val))
                    except Exception:
                        return pd.NaT
                converted = df[col_to_convert].apply(_to_td)
            elif new_dtype in ["string", "object"]:
                converted = df[col_to_convert].astype(str)
            elif new_dtype == "category":
                converted = df[col_to_convert].astype('category')
            elif new_dtype in ["int64", "float64"]:
                converted = pd.to_numeric(df[col_to_convert], errors='coerce').astype(new_dtype)
            else:
                converted = df[col_to_convert].astype(new_dtype)
            df[col_to_convert] = converted
            st.session_state.df = df
            st.success(f"✅ Converted `{col_to_convert}` to `{new_dtype}`")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Conversion failed: {e}")

    return df


def show_column_classifier(df):
    all_cols = df.columns.tolist()

    auto_dt = df.select_dtypes(include=['datetime','datetimetz','timedelta']).columns.tolist()
    for col in df.select_dtypes(include=['object']):
        if len(df) > 0 and isinstance(df[col].iloc[0], (datetime.date, datetime.time)):
            if col not in auto_dt:
                auto_dt.append(col)

    auto_num = df.select_dtypes(include=[np.number]).columns.tolist()
    auto_num = [c for c in auto_num if c not in auto_dt]
    auto_cat = [c for c in all_cols if c not in auto_num and c not in auto_dt]

    st.markdown("---")
    st.markdown("## 🏷️ Column Classification")
    mode = st.radio("Detection mode", ["🤖 Auto-detect","✏️ Manual selection"],
                    horizontal=True, label_visibility="collapsed")
    st.markdown('<div class="classifier-box">', unsafe_allow_html=True)

    suffix = "" if "🤖" in mode else "_m"
    c1, c2, c3 = st.columns(3)
    with c1: confirmed_num = st.multiselect("Numeric Columns",   all_cols, default=auto_num, key=f"cls_num{suffix}")
    with c2: confirmed_cat = st.multiselect("Categorical Columns", all_cols, default=auto_cat, key=f"cls_cat{suffix}")
    with c3: confirmed_dt  = st.multiselect("Date/Time Columns",  all_cols, default=auto_dt,  key=f"cls_dt{suffix}")
    st.markdown('</div>', unsafe_allow_html=True)

    overlap = []
    if set(confirmed_num) & set(confirmed_cat): overlap.append("Numeric & Categorical")
    if set(confirmed_num) & set(confirmed_dt):  overlap.append("Numeric & Date/Time")
    if set(confirmed_cat) & set(confirmed_dt):  overlap.append("Categorical & Date/Time")
    if overlap:
        st.warning(f"⚠️ Overlap detected between: {', '.join(overlap)}")

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("✅ Confirm & Proceed to Analysis", disabled=bool(overlap)):
            st.session_state.num_cols = confirmed_num
            st.session_state.cat_cols = confirmed_cat
            st.session_state.dt_cols  = confirmed_dt
            st.session_state.page     = "analysis"
            # Only reset charts when NOT in edit mode — preserve saved charts
            if "editing_session_id" not in st.session_state:
                st.session_state.charts   = []
                st.session_state.selected_analyses = []
            st.rerun()
