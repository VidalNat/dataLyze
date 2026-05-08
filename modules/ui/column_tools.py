"""
modules/ui/column_tools.py -- Column type classification and data transformation UI.
Provides two main UI components used on the upload page:
  show_column_classifier(df):
    Renders a table where the user confirms or overrides the auto-detected
    type of each column (Numeric / Categorical / Date-Time / Ignore).
    After confirmation, writes the classified lists to session_state.
  show_dtype_transformer(df):
    Inspects current dtypes, previews conversions, and safely transforms columns
    with robust date/time parsing (European DD/MM/YYYY standard) and format inference.
"""
import streamlit as st
import numpy as np
import pandas as pd
import datetime
import warnings

warnings.filterwarnings("ignore", category=UserWarning, module="pandas")

# ── Robust Parsing Helpers ──────────────────────────────────────────────────
def _robust_to_datetime(series: pd.Series) -> pd.Series:
    """Parse inconsistent date/time strings with European (DD/MM/YYYY) priority."""
    try:
        return pd.to_datetime(series, format="mixed", dayfirst=True, errors="coerce")
    except TypeError:
        return pd.to_datetime(series, dayfirst=True, errors="coerce")

def _robust_to_date(series: pd.Series) -> pd.Series:
    """Convert to date strings formatted as DD/MM/YYYY (European standard)."""
    dt = _robust_to_datetime(series)
    return dt.dt.strftime("%d/%m/%Y")

def _robust_to_time(series: pd.Series) -> pd.Series:
    """Parse HH:MM, HH:MM:SS, or full datetime strings, returning HH:MM:SS."""
    src = series.astype(str).str.strip()
    try:
        parsed = pd.to_datetime(src, format="mixed", errors="coerce")
    except TypeError:
        parsed = pd.to_datetime(src, errors="coerce")
    
    if parsed.notna().any():
        return parsed.dt.strftime("%H:%M:%S")
    return pd.Series([None] * len(series), dtype="object")

def show_dtype_transformer(df: pd.DataFrame) -> pd.DataFrame:
    st.markdown("---")
    st.markdown("## 🔍 Data Type Inspector & Transformer")
    
    # ── Inspector Table ─────────────────────────────────────────────────────
    dtype_df = pd.DataFrame({
        "Column": df.columns,
        "Current Dtype": df.dtypes.astype(str),
        "Sample Value": [str(df[col].iloc[0]) if len(df) > 0 else "–" for col in df.columns]
    }).reset_index(drop=True)
    st.dataframe(dtype_df, use_container_width=True, hide_index=True)

    st.markdown("### 🛠️ Transform Column Types")
    col_to_convert = st.selectbox("Select column to transform", df.columns, key="dtype_col")
    current_dtype = str(df[col_to_convert].dtype)

    target_options = [
        "object", "string", "int64", "float64", "bool", "category",
        "datetime64[ns]", "date (DD/MM/YYYY)", "time (HH:MM:SS)", "timedelta64[ns]"
    ]

    # Safe default index selection
    default_idx = 0
    if "int" in current_dtype and "int64" in target_options:
        default_idx = target_options.index("int64")
    elif "float" in current_dtype and "float64" in target_options:
        default_idx = target_options.index("float64")
    elif "datetime" in current_dtype and "datetime64[ns]" in target_options:
        default_idx = target_options.index("datetime64[ns]")
    elif "bool" in current_dtype and "bool" in target_options:
        default_idx = target_options.index("bool")
    elif current_dtype in target_options:
        default_idx = target_options.index(current_dtype)

    new_dtype = st.selectbox(
        f"Convert `{col_to_convert}` from `{current_dtype}` to:",
        options=target_options,
        index=default_idx,
        key=f"dtype_target_{col_to_convert}"
    )

    # ── Preview Conversion (Persisted & Robust) ─────────────────────────────
    preview_key = f"preview_dtype_{col_to_convert}"   # session state result key
    preview_btn_key = f"btn_{preview_key}"             # widget key (Streamlit owns this)
    if st.button("🔍 Preview Conversion", key=preview_btn_key):
        with st.spinner("Calculating preview stats..."):
            src = df[col_to_convert]
            try:
                if new_dtype == "datetime64[ns]":
                    test = _robust_to_datetime(src)
                elif new_dtype.startswith("date"):
                    test = _robust_to_date(src)
                elif new_dtype.startswith("time"):
                    test = _robust_to_time(src)
                elif new_dtype == "timedelta64[ns]":
                    test = pd.to_timedelta(src.astype(str), errors="coerce")
                elif new_dtype in ( "int64 ",  "float64 "):
                    test = pd.to_numeric(src, errors= "coerce ").astype(new_dtype)
                elif new_dtype == "bool":
                    mapped = src.astype(str).str.strip().str.lower().map(
                        {"true": True, "1": True, "yes": True, "false": False, "0": False, "no": False}
                    )
                    test = mapped
                else:
                    test = src.astype(new_dtype)
                
                n_null_before = int(src.isna().sum())
                n_null_after = int(pd.isna(test).sum())
                new_nulls = max(0, n_null_after - n_null_before)
                success_rate = ((len(src) - n_null_after) / len(src)) * 100 if len(src) > 0 else 0
                
                # Store in session state so it persists across interactions
                st.session_state[preview_key] = {
                    "success_rate": success_rate,
                    "converted": len(src) - n_null_after,
                    "new_nulls": new_nulls,
                    "sample": test.head(3).tolist()
                }
            except Exception as e:
                st.session_state[preview_key] = {"error": str(e)}

    # Render persisted preview if it exists
    if preview_key in st.session_state:
        res = st.session_state[preview_key]
        if "error" in res:
            st.error(f"❌ Preview failed: {res['error']}")
        else:
            c1, c2, c3 = st.columns(3)
            c1.metric("Success Rate", f"{res['success_rate']:.1f}%")
            c2.metric("Values Converted", res['converted'])
            c3.metric("⚠️ Will Become Null", res['new_nulls'], delta=None if res['new_nulls'] == 0 else "-")
            
            st.caption("🔎 Sample of converted values:")
            st.code(str(res['sample']))
            
            if res['new_nulls'] > 0:
                st.warning(f"⚠️ {res['new_nulls']} value(s) couldn't convert and will become `NaT`/`NaN`.")
            else:
                st.success("✅ All values converted successfully. Safe to apply.")

    # ── Apply Transformation ────────────────────────────────────────────────
    apply_key = f"apply_dtype_{col_to_convert}"
    if st.button(" Apply Transformation", key=apply_key):
        with st.spinner(f"Converting `{col_to_convert}` to `{new_dtype}`…"):
            try:
                src = df[col_to_convert]
                n_null_before = int(src.isna().sum())

                if new_dtype == "datetime64[ns]":
                    converted = _robust_to_datetime(src)
                elif new_dtype.startswith("date"):
                    converted = _robust_to_date(src)
                elif new_dtype.startswith("time"):
                    converted = _robust_to_time(src)
                elif new_dtype == "timedelta64[ns]":
                    src_str = src.astype(str)
                    if len(src) > 0 and isinstance(src.iloc[0], datetime.time):
                        src_str = src.apply(lambda v: f"{v.hour}:{v.minute:02d}:{v.second:02d}" if isinstance(v, datetime.time) else str(v))
                    converted = pd.to_timedelta(src_str, errors="coerce")
                elif new_dtype in ("string", "object"):
                    converted = src.astype(str)
                elif new_dtype == "category":
                    converted = src.astype("category")
                elif new_dtype == "bool":
                    mapped = src.astype(str).str.strip().str.lower().map(
                        {"true": True, "1": True, "yes": True, "false": False, "0": False, "no": False}
                    )
                    if mapped.isna().all():
                        raise ValueError("No recognisable boolean values (expected true/false/1/0/yes/no).")
                    converted = mapped
                elif new_dtype in ("int64", "float64"):
                    converted = pd.to_numeric(src, errors="coerce").astype(new_dtype)
                else:
                    converted = src.astype(new_dtype)

                df[col_to_convert] = converted
                st.session_state.df = df
                
                n_null_after = int(df[col_to_convert].isna().sum())
                new_nulls = max(0, n_null_after - n_null_before)
                
                msg = f"✅ Converted `{col_to_convert}` → `{new_dtype}`"
                if new_nulls:
                    msg += f" ({new_nulls} invalid value(s) set to null)"
                st.toast(msg, icon="🔄")
                
                # Clear preview cache since data changed
                if preview_key in st.session_state:
                    del st.session_state[preview_key]
                st.rerun()
            except Exception as e:
                st.error(f"❌ Conversion failed: {e}")

    return df

def show_column_classifier(df):
    """Existing classifier logic (unchanged)"""
    all_cols = df.columns.tolist()
    auto_dt = df.select_dtypes(include=["datetime", "datetimetz", "timedelta"]).columns.tolist()
    for col in df.select_dtypes(include=["object"]):
        if len(df) > 0 and isinstance(df[col].iloc[0], (datetime.date, datetime.time)):
            if col not in auto_dt:
                auto_dt.append(col)

    auto_num = df.select_dtypes(include=[np.number]).columns.tolist()
    auto_num = [c for c in auto_num if c not in auto_dt]
    auto_cat = [c for c in all_cols if c not in auto_num and c not in auto_dt]

    st.markdown("---")
    st.markdown("## 🏷️ Column Classification")
    mode = st.radio("Detection mode", ["🤖 Auto-detect", "✏️ Manual selection"],
                    horizontal=True, label_visibility="collapsed")
    st.markdown('<div class="classifier-box">', unsafe_allow_html=True)

    suffix = "" if "🤖" in mode else "_m"
    c1, c2, c3 = st.columns(3)
    with c1: confirmed_num = st.multiselect("Numeric Columns", all_cols, default=auto_num, key=f"cls_num{suffix}")
    with c2: confirmed_cat = st.multiselect("Categorical Columns", all_cols, default=auto_cat, key=f"cls_cat{suffix}")
    with c3: confirmed_dt = st.multiselect("Date/Time Columns", all_cols, default=auto_dt, key=f"cls_dt{suffix}")
    st.markdown("</div>", unsafe_allow_html=True)

    overlap = []
    if set(confirmed_num) & set(confirmed_cat): overlap.append("Numeric & Categorical")
    if set(confirmed_num) & set(confirmed_dt): overlap.append("Numeric & Date/Time")
    if set(confirmed_cat) & set(confirmed_dt): overlap.append("Categorical & Date/Time")
    if overlap:
        st.warning(f"⚠️ Overlap detected between: {', '.join(overlap)}")

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("✅ Confirm & Proceed to Analysis", disabled=bool(overlap)):
        st.session_state.num_cols = confirmed_num
        st.session_state.cat_cols = confirmed_cat
        st.session_state.dt_cols = confirmed_dt
        st.session_state.page = "analysis"
        if "editing_session_id" not in st.session_state:
            st.session_state.charts = []
            st.session_state.selected_analyses = []
        st.rerun()