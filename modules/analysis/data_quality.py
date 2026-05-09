"""
modules/analysis/data_quality.py -- Data quality analysis runner.
================================================================

Detects and provides inline cleaning tools for two common data problems:

  1. Missing Values -- identifies columns with null/NaN values, renders a
     summary table and heatmap, and provides one-click cleaning actions.

  2. Duplicate Rows -- detects duplicate rows (optionally scoped to a primary
     key column), shows the duplicates in an expandable table, and provides
     bulk or row-level deletion controls.

⚠️  IMPORTANT -- this module MUST NOT be called inside an st.form() block.
    It renders its own st.button() widgets. If called inside a form, Streamlit
    will raise a DuplicateWidgetID error because forms wrap their own submit
    button around everything inside them.

    pages/analysis.py handles this with a special code path -- data_quality is
    listed in _NO_FORM so it bypasses the standard analysis form entirely.

Returns:
    list of (title: str, fig: Figure) tuples -- up to three charts:
      - "Missing % by Column"   -- bar chart of missing percentages
      - "Missing Values Map"    -- heatmap of null positions (sample of 100 rows)
      - "Duplicate Rows Summary" -- donut chart of unique vs duplicate row counts

All cleaning actions modify st.session_state.df in-place and call st.rerun()
to refresh the page with the updated dataset.
"""

import streamlit as st
import plotly.express as px
from modules.database import log_activity
from modules.charts import chart_layout, DANGER


def run_data_quality(df):
    """
    Render interactive data quality widgets and return summary charts.

    Args:
        df: Working DataFrame -- read from st.session_state.df by the caller.

    Returns:
        list of (title: str, fig: Figure) tuples (up to 3 charts).
    """
    charts = []

    # ─────────────────────────────────────────────────────────────────────────
    # Section 1: Missing Values
    # ─────────────────────────────────────────────────────────────────────────
    miss_total = int(df.isnull().sum().sum())
    st.markdown("### 🕳️ Missing Values")

    if miss_total == 0:
        st.success("✅ No missing values found -- dataset is complete!")
    else:
        # Build a summary table: column name, count of nulls, percentage.
        mc = df.isnull().sum().reset_index()
        mc.columns = ["Column", "Missing Count"]
        mc["Missing %"] = (mc["Missing Count"] / len(df) * 100).round(2)
        mc = mc[mc["Missing Count"] > 0].sort_values("Missing Count", ascending=False)

        st.markdown(f"**{miss_total:,} missing cells** across {len(mc)} column(s)")
        st.dataframe(mc, use_container_width=True, hide_index=True)

        # Expandable preview of the actual rows that contain any null.
        with st.expander(
            f"👁️ View rows with missing values ({int(df.isnull().any(axis=1).sum())} rows)"
        ):
            st.dataframe(df[df.isnull().any(axis=1)].head(200), use_container_width=True)

        # ── Cleaning controls ─────────────────────────────────────────────────
        st.markdown("**🧹 Clean missing values:**")
        cl1, cl2, cl3 = st.columns(3)

        with cl1:
            if st.button("Drop ALL rows with any NA", key="dq_dropna_all"):
                before = len(st.session_state.df)
                st.session_state.df = st.session_state.df.dropna()
                removed = before - len(st.session_state.df)
                log_activity(
                    st.session_state.get("user_id", 0),
                    "dropna_all", f"removed {removed} rows")
                st.success(
                    f"✅ Removed {removed:,} rows. "
                    f"Dataset now has {len(st.session_state.df):,} rows.")
                st.rerun()

        with cl2:
            # Column-scoped NA drop -- pick which column's nulls to remove.
            col_to_drop_na = st.selectbox(
                "Drop NA in column:", mc["Column"].tolist(),
                key="dq_col_na", label_visibility="collapsed")

        with cl3:
            if st.button(
                f"Drop rows where '{col_to_drop_na}' is NA", key="dq_dropna_col"
            ):
                before = len(st.session_state.df)
                st.session_state.df = st.session_state.df.dropna(
                    subset=[col_to_drop_na])
                removed = before - len(st.session_state.df)
                log_activity(
                    st.session_state.get("user_id", 0),
                    "dropna_col", f"col={col_to_drop_na} removed={removed}")
                st.success(
                    f"✅ Removed {removed:,} rows where '{col_to_drop_na}' was NA.")
                st.rerun()

        # ── Missing % bar chart ───────────────────────────────────────────────
        fig_mc = px.bar(
            mc, x="Column", y="Missing %",
            title="Missing % by Column",
            color="Missing %", color_continuous_scale=DANGER, text_auto=".1f")
        fig_mc.update_layout(**chart_layout())
        charts.append(("Missing % by Column", fig_mc))

        # ── Missing values heatmap (sampled to 100 rows for performance) ──────
        sample = df.sample(min(100, len(df))) if len(df) > 100 else df
        fig_map = px.imshow(
            sample.isnull().astype(int),
            title="Missing Values Map",
            color_continuous_scale=["rgba(0,0,0,0)", "#ef4444"],
            aspect="auto")
        fig_map.update_layout(**chart_layout())
        charts.append(("Missing Values Map", fig_map))

    st.markdown("---")

    # ─────────────────────────────────────────────────────────────────────────
    # Section 2: Duplicate Rows
    # ─────────────────────────────────────────────────────────────────────────
    st.markdown("### 🔁 Duplicate Rows")

    # Primary key column selector.
    # Using a primary key (e.g. Order ID) detects "true" duplicates based on
    # a unique identifier rather than full-row comparison -- far more accurate
    # for real-world datasets where most columns are not strictly unique.
    st.markdown(
        "**🔑 Primary Key Column (optional but recommended)**\n\n"
        "A primary key uniquely identifies each row -- think *Order ID*, *Customer ID*, "
        "*Transaction Number*. When selected, duplicates are detected based on that column "
        "alone, which is far more accurate than comparing every field. "
        "Leave as *None* to check all columns together."
    )
    pk_options = ["None (compare all columns)"] + df.columns.tolist()
    pk_choice = st.selectbox(
        "Select primary key column:",
        options=pk_options,
        key="dq_pk_col",
        help="Rows sharing the same primary key value are true duplicates.")

    pk_cols   = None if pk_choice == "None (compare all columns)" else [pk_choice]
    dup_mask  = df.duplicated(subset=pk_cols, keep=False)  # Marks ALL copies.
    dup_count = int(df.duplicated(subset=pk_cols).sum())   # Counts extras only.

    if pk_cols:
        st.caption(
            f"Detecting duplicates by **{pk_choice}** -- {dup_count:,} duplicate(s) found.")
    else:
        st.caption(
            f"Detecting duplicates across **all columns** -- {dup_count:,} duplicate(s) found.")

    if dup_count == 0:
        st.success("✅ No duplicate rows found!")
    else:
        st.markdown(f"**{dup_count:,} duplicate rows** detected (keeping first occurrence).")

        dup_rows = df[dup_mask].sort_values(by=df.columns.tolist())
        with st.expander(
            f"👁️ View duplicate rows ({len(dup_rows)} rows including originals)"
        ):
            st.dataframe(dup_rows.head(500), use_container_width=True)

            # Row-level deletion -- user picks specific indices to delete.
            st.markdown("**Delete individual rows** (by row index):")
            del_idx = st.multiselect(
                "Select row indices to delete:", dup_rows.index.tolist(),
                key="dq_del_idx",
                help="Original DataFrame row indices -- pick specific duplicates to remove.")
            if st.button("🗑️ Delete selected rows", key="dq_del_selected") and del_idx:
                st.session_state.df = (
                    st.session_state.df.drop(index=del_idx).reset_index(drop=True))
                log_activity(
                    st.session_state.get("user_id", 0),
                    "delete_rows_manual", f"deleted indices: {del_idx[:20]}")
                st.success(f"✅ Deleted {len(del_idx)} row(s).")
                st.rerun()

        # Bulk drop controls -- keep first vs keep last.
        drop1, drop2 = st.columns(2)
        with drop1:
            if st.button("Drop ALL duplicates (keep first)", key="dq_drop_dup"):
                before = len(st.session_state.df)
                st.session_state.df = (
                    st.session_state.df
                    .drop_duplicates(subset=pk_cols, keep="first")
                    .reset_index(drop=True))
                removed = before - len(st.session_state.df)
                log_activity(
                    st.session_state.get("user_id", 0),
                    "drop_duplicates", f"removed {removed} rows pk={pk_choice}")
                st.success(f"✅ Removed {removed:,} duplicate rows.")
                st.rerun()

        with drop2:
            if st.button("Drop ALL duplicates (keep last)", key="dq_drop_dup_last"):
                before = len(st.session_state.df)
                st.session_state.df = (
                    st.session_state.df
                    .drop_duplicates(subset=pk_cols, keep="last")
                    .reset_index(drop=True))
                removed = before - len(st.session_state.df)
                log_activity(
                    st.session_state.get("user_id", 0),
                    "drop_duplicates_last",
                    f"removed {removed} rows pk={pk_choice}")
                st.success(f"✅ Removed {removed:,} duplicate rows (kept last).")
                st.rerun()

    # ── Row uniqueness donut chart -- always shown ──────────────────────────────
    total        = len(df)
    unique_count = total - dup_count
    fig_pie = px.pie(
        values=[unique_count, dup_count],
        names=["Unique", "Duplicate"],
        title=f"Row Uniqueness -- {dup_count} duplicates out of {total:,}",
        color_discrete_sequence=["#4f6ef7", "#ef4444"],
        hole=0.48)
    fig_pie.update_layout(**chart_layout())
    charts.append(("Duplicate Rows Summary", fig_pie))

    return charts
