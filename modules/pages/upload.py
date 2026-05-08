"""
modules/pages/upload.py -- File upload and column classification page.
======================================================================

Handles the full data ingestion pipeline:
    1. File upload (CSV or Excel via st.file_uploader)
    2. For Excel: multi-sheet browser / unified table builder (excel_loader.py)
    3. For CSV: direct pandas read_csv into session_state.df
    4. Data-type inspection and transformation (column_tools.py)
    5. Column classification (numeric / categorical / date-time)
    6. "Confirm & Proceed to Analysis" button → navigates to analysis page

Bug fix applied:
    _clear_excel_state("") -- the original condition not k.endswith("") was
    always False, so calling with no argument never cleared any state.
    Fixed by adding: not new_file_name or not k.endswith(new_file_name)

CONTRIBUTING -- to add a new file type:
    Add a branch after the `is_excel()` check in page_upload().
    Read the file into a pandas DataFrame and write it to st.session_state.df.
    Then call _show_analysis_pipeline(df, filename) to continue the normal flow.

Fixes:
  - Lytrize logo at top (#10)
  - Preserves editing_session_id when re-uploading in edit mode (#8)
  - _clear_excel_state() now correctly clears all _xl_sheets_ keys when
    switching away from Excel (not new_file_name guard added).
"""

import streamlit as st
import pandas as pd
from html import escape
from modules.ui.column_manager import show_column_manager
from modules.ui.column_tools import show_dtype_transformer, show_column_classifier
from modules.ui.excel_loader import show_excel_loader
from modules.ui.css import inject_footer, render_logo, render_page_steps
from modules.analysis.data_quality import run_data_quality
from modules.utils.perf import read_csv_fast, mem_mb


def _is_excel(name: str) -> bool:
    return name.lower().endswith((".xlsx", ".xls"))


def _uploaded_signature(uploaded) -> str:
    file_id = getattr(uploaded, "file_id", None)
    size = getattr(uploaded, "size", None)
    if file_id:
        return f"{uploaded.name}:{size}:{file_id}"
    return f"{uploaded.name}:{size}:{len(uploaded.getbuffer())}"


def page_upload():
    # Top nav row
    nc1, nc2 = st.columns([10, 1.5])
    with nc1:
        render_logo()
    with nc2:
        if st.button("← Home", use_container_width=True):
            st.session_state.page = "home"; st.rerun()

    render_page_steps("upload")
    # Show editing context if in edit mode
    if "editing_session_id" in st.session_state:
        fname = st.session_state.get("editing_file_name", "the original file")
        st.info(
            f"✏️ **Edit mode** -- re-upload **{fname}** to add more charts to the saved session. "
            f"Your existing charts are preserved.")

    uploaded = st.file_uploader(
        "CSV or Excel (single or multi-sheet)",
        type=["csv", "xlsx", "xls"]
    )

    if not uploaded:
        inject_footer()
        return

    is_excel     = _is_excel(uploaded.name)
    file_sig     = _uploaded_signature(uploaded)
    file_changed = (
        st.session_state.get("file_name") != uploaded.name or
        st.session_state.get("file_signature") != file_sig
    )

    if not is_excel:
        if "df" not in st.session_state or file_changed:
            with st.spinner("Reading & optimising file…"):
                raw_size = getattr(uploaded, "size", 0) / 1_048_576
                df       = read_csv_fast(uploaded)
                opt_mb   = mem_mb(df)
                if raw_size > 50:
                    st.toast(
                        f"✅ Loaded {raw_size:.0f} MB → ~{opt_mb:.0f} MB in-memory after dtype optimisation",
                        icon="✅",
                    )
            st.session_state.df        = df
            st.session_state.file_name = uploaded.name
            st.session_state.file_signature = file_sig
            _clear_excel_state()
        else:
            df = st.session_state.df
        _show_analysis_pipeline(df, uploaded.name)

    else:
        if file_changed:
            st.session_state.pop("df", None)
            _clear_excel_state(uploaded.name)
            st.session_state.file_name = uploaded.name
            st.session_state.file_signature = file_sig

        schema_info = st.session_state.get("_unified_table_info")
        if schema_info and "df" in st.session_state:
            safe_fact = escape(str(schema_info["fact"]))
            safe_dims = [escape(str(d)) for d in schema_info["dims"]]
            st.markdown(
                '<div style="background:rgba(16,185,129,0.10);border:1px solid rgba(16,185,129,0.25);'
                'border-radius:12px;padding:0.8rem 1.1rem;margin-bottom:1rem;">'
                '&#127775; <b>Unified table active</b> -- '
                f'Fact: <b>{safe_fact}</b> joined with '
                + ", ".join(f"<b>{d}</b>" for d in safe_dims) +
                f' &nbsp;·&nbsp; {schema_info["shape"][0]:,} rows x {schema_info["shape"][1]} cols'
                '</div>',
                unsafe_allow_html=True
            )

        if "df" not in st.session_state:
            df = show_excel_loader(uploaded)
            if df is not None:
                st.session_state.df = df
                st.rerun()
        else:
            if st.button("⚙️ Edit Excel Configuration", key="_xl_edit_config"):
                st.session_state.pop("df", None)
                st.rerun()
            _show_analysis_pipeline(st.session_state.df, uploaded.name)


def _show_analysis_pipeline(df: pd.DataFrame, file_name: str):
    st.markdown("---")
    st.markdown(
        f"**{file_name}** — {df.shape[0]:,} rows × {df.shape[1]} columns"
    )
    st.dataframe(df.head(), use_container_width=True)

    # ── Data Quality (fragment — reruns independently from the rest) ──────────
    st.markdown("### 🧹 Data Quality")
    st.caption(
        "Review missing values and duplicate rows before analysis. "
        "Fixing data issues here gives you cleaner charts and more reliable insights."
    )
    run_data_quality(df)   # @st.fragment — only this block reruns on widget changes

    st.markdown("---")

    df = show_column_manager(df)
    df = show_dtype_transformer(df)
    show_column_classifier(df)

    with st.expander("📖 Describe Your Columns (optional -- improves auto-insights)", expanded=False):
        st.markdown(
            "Describe what each column means. These appear in chart insights "
            "to give context-aware observations. Leave blank to skip."
        )
        col_descs = st.session_state.get("col_descriptions", {})
        for col in df.columns:
            col_descs[col] = st.text_input(
                f"`{col}`",
                value=col_descs.get(col, ""),
                key=f"coldesc_{col}",
                placeholder="e.g. 'Total revenue in USD per transaction'"
            )
        if st.button("💾 Save Column Descriptions", key="save_col_descs"):
            st.session_state.col_descriptions = col_descs
            st.toast("Column descriptions saved.", icon="💾")


def _clear_excel_state(new_file_name: str = ""):
    """
    Remove all _xl_sheets_* keys from session_state that don't belong to new_file_name.

    When called with no argument (CSV upload replacing Excel), new_file_name is ""
    and every key starting with _xl_sheets_ must be removed.

    FIX: The original condition  `not k.endswith("")`  is always False (every
    string ends with ""), so calling _clear_excel_state() with no argument was
    a no-op. The guard `not new_file_name` now ensures all keys are cleared
    when switching away from an Excel file entirely.
    """
    keys_to_delete = [
        k for k in list(st.session_state.keys())
        if k.startswith("_xl_sheets_") and (not new_file_name or not k.endswith(new_file_name))
    ]
    for k in keys_to_delete:
        del st.session_state[k]
    st.session_state.pop("_unified_table_info", None)
