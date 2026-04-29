"""
modules/analysis/__init__.py
Bulletproof config — ZERO conditional widget display.
Top N → number_input(0=all). Dual Y → selectbox(None+cols).
Nothing shows/hides on interaction. Generate reads from session_state.
"""

import uuid
import streamlit as st

from modules.analysis.descriptive  import run_descriptive
from modules.analysis.statistical  import run_statistical
from modules.analysis.distribution import run_distribution
from modules.analysis.correlation  import run_correlation
from modules.analysis.categorical  import run_categorical
from modules.analysis.pie_chart    import run_pie_chart
from modules.analysis.time_series  import run_time_series
from modules.analysis.data_quality import run_data_quality
from modules.analysis.outlier      import run_outlier, OUTLIER_HELP
from modules.charts import PALETTES, num_cols as _num_cols, cat_cols as _cat_cols, dt_cols as _dt_cols

ANALYSIS_OPTIONS = [
    {"id":"descriptive",  "icon":"🗂️", "name":"Descriptive",      "desc":"Stats table — numeric cols"},
    {"id":"data_quality", "icon":"🧹", "name":"Data Quality",      "desc":"Missing values & duplicates"},
    {"id":"statistical",  "icon":"📐", "name":"Statistical",       "desc":"Mean, std, min, max"},
    {"id":"distribution", "icon":"📊", "name":"Distribution",      "desc":"Histograms & box plots"},
    {"id":"correlation",  "icon":"🔗", "name":"Correlation",       "desc":"Heatmap & scatter matrix"},
    {"id":"categorical",  "icon":"🏷️", "name":"Categorical Bar",   "desc":"Vertical & horizontal bars"},
    {"id":"pie_chart",    "icon":"🍩", "name":"Pie & Donut",       "desc":"Proportion & share analysis"},
    {"id":"time_series",  "icon":"⏱️", "name":"Time Series",       "desc":"Trends & time patterns"},
    {"id":"outlier",      "icon":"🚨", "name":"Outlier Detection", "desc":"IQR-based anomaly analysis"},
]

_RUNNERS = {
    "descriptive":  run_descriptive,
    "data_quality": run_data_quality,
    "statistical":  run_statistical,
    "distribution": run_distribution,
    "correlation":  run_correlation,
    "categorical":  run_categorical,
    "pie_chart":    run_pie_chart,
    "time_series":  run_time_series,
    "outlier":      run_outlier,
}

_NEEDS_AXES = {"statistical","distribution","correlation","categorical",
               "pie_chart","time_series","outlier"}
_NO_FORM    = {"data_quality"}

_AGG_FUNCS  = {"Mean (Avg)":"mean","Sum":"sum","Median":"median",
               "Count":"count","Min":"min","Max":"max"}
_DATE_PARTS = {
    "None": None, "Year":"Y", "Quarter":"Q", "Month (number)":"M",
    "Month Name":"month_name", "Weekday Name":"weekday_name", "Day":"D", "Hour":"H",
}

# ── Session-state helpers ──────────────────────────────────────────────────────
def _sk(aid, key):  return f"_cfg_{aid}_{key}"
def _g(aid, key, default=None): return st.session_state.get(_sk(aid,key), default)


def render_config_panel(aid, df):
    """
    Render configuration widgets for analysis `aid`.
    ALL widgets are always visible — no show/hide conditionals on interaction.
    Returns nothing; caller reads config with _collect_kwargs().
    """
    num, cat, dt, all_cols = _num_cols(), _cat_cols(), _dt_cols(), df.columns.tolist()
    NONE = "None"

    # Palette — always shown
    st.selectbox("🎨 Colour Palette", list(PALETTES.keys()), key=_sk(aid,"palette"))
    st.markdown("---")

    # ── Descriptive ───────────────────────────────────────────────────────────
    if aid == "descriptive":
        st.info("No configuration needed — outputs a full stats table.")

    # ── Statistical ───────────────────────────────────────────────────────────
    elif aid == "statistical":
        c1, c2, c3 = st.columns(3)
        with c1: st.multiselect("Group by (optional)", cat, max_selections=1, key=_sk(aid,"x"))
        with c2: st.multiselect("Metrics", num, default=num[:4], key=_sk(aid,"y"))
        with c3: st.selectbox("Aggregation", list(_AGG_FUNCS.keys()), key=_sk(aid,"agg"))

    # ── Distribution ──────────────────────────────────────────────────────────
    elif aid == "distribution":
        c1, c2 = st.columns(2)
        with c1: st.multiselect("Numeric columns", num, default=num[:4], key=_sk(aid,"x"))
        with c2: st.multiselect("Colour by (optional)", cat, max_selections=1, key=_sk(aid,"color"))

    # ── Correlation ───────────────────────────────────────────────────────────
    elif aid == "correlation":
        c1, c2 = st.columns(2)
        with c1: st.multiselect("Columns", num, default=num, key=_sk(aid,"x"))
        with c2: st.multiselect("Additional (optional)", num, key=_sk(aid,"y"))

    # ── Categorical & Pie ─────────────────────────────────────────────────────
    elif aid in ("categorical","pie_chart"):
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.multiselect("Dimension columns", cat, default=cat[:2], key=_sk(aid,"x"))
        with c2: st.multiselect("Metric columns (optional)", num, key=_sk(aid,"y"))
        with c3: st.selectbox("Aggregation", list(_AGG_FUNCS.keys()), key=_sk(aid,"agg"))
        with c4: st.selectbox("Sort", ["Value ↓","Value ↑","Category A→Z","Category Z→A"],
                              key=_sk(aid,"sort"))
        st.markdown("---")

        # Direction (categorical only) — always visible
        if aid == "categorical":
            st.selectbox("📊 Chart Direction",
                         ["Vertical (Column chart)","Horizontal (Bar chart)"],
                         key=_sk(aid,"direction"),
                         help="Vertical = column chart. Horizontal = bar chart with values outside tips.")

        # ── Top N — always visible number_input, 0 = all ──────────────────────
        st.markdown("**🔝 Top N Categories**")
        st.caption("Enter how many top categories to show. Set to 0 to show all categories.")
        st.number_input(
            "Top N (0 = show all)",
            min_value=0, max_value=200, step=1,
            value=0,
            key=_sk(aid,"top_n"),
            help="0 = no limit. e.g. 10 = show only the 10 highest-value categories.")

        # ── Dual Y-axis — always-visible selectbox ────────────────────────────
        if aid == "categorical":
            st.markdown("---")
            st.markdown("**📊 Dual Y-Axis (Secondary metric as line overlay)**")
            st.caption("Choose a secondary metric to overlay as a line on a second Y-axis. Select 'None' to disable.")
            dual_opts = [NONE] + [m for m in num]
            st.selectbox("Secondary Y-Axis metric",
                         dual_opts,
                         key=_sk(aid,"dual_y"),
                         help="The primary metric shows as bars; secondary shows as a line on the right Y-axis.")

    # ── Time Series ───────────────────────────────────────────────────────────
    elif aid == "time_series":
        dt_candidates = dt if dt else all_cols
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.multiselect("Date / Time column", dt_candidates,
                           default=dt_candidates[:1] if dt_candidates else [],
                           max_selections=1, key=_sk(aid,"x"))
        with c2:
            st.multiselect("Primary metric(s)", num, default=num[:2], key=_sk(aid,"y"))
        with c3:
            st.selectbox("Date grouping", list(_DATE_PARTS.keys()), key=_sk(aid,"date_part"))
        with c4:
            st.selectbox("Aggregation", list(_AGG_FUNCS.keys()), key=_sk(aid,"agg"))
        st.markdown("---")

        # ── Dual Y — always-visible selectbox ────────────────────────────────
        st.markdown("**📊 Dual Y-Axis (Secondary metric as dashed line)**")
        st.caption("Choose a secondary metric on the right Y-axis. Select 'None' to disable.")
        dual_opts_ts = [NONE] + num
        st.selectbox("Secondary Y-Axis metric",
                     dual_opts_ts,
                     key=_sk(aid,"dual_y_ts"),
                     help="Adds a second line on the right axis. Pick the same as primary = disabled.")

    # ── Outlier ───────────────────────────────────────────────────────────────
    elif aid == "outlier":
        c1, c2 = st.columns(2)
        with c1: st.multiselect("Columns to analyse", num, default=num[:4], key=_sk(aid,"x"))
        with c2: st.multiselect("Group by (optional)", cat, max_selections=1, key=_sk(aid,"grp"))


def _collect_kwargs(aid, df):
    """Read config from session_state and return kwargs dict for the runner."""
    num, cat, dt, all_cols = _num_cols(), _cat_cols(), _dt_cols(), df.columns.tolist()
    NONE = "None"

    pal_label = _g(aid,"palette", list(PALETTES.keys())[0])
    palette   = PALETTES.get(pal_label, list(PALETTES.values())[0])
    kwargs    = {"palette": palette}

    _sort_map = {"Value ↓":"Value (Desc)","Value ↑":"Value (Asc)",
                 "Category A→Z":"Category (A-Z)","Category Z→A":"Category (Z-A)"}

    if aid == "statistical":
        x   = _g(aid,"x",[])
        y   = _g(aid,"y", num[:4]) or num
        agg = _AGG_FUNCS.get(_g(aid,"agg","Mean (Avg)"),"mean")
        kwargs.update(x_cols=x or None, y_cols=y, agg=agg)

    elif aid == "distribution":
        x     = _g(aid,"x", num[:4]) or num[:4]
        color = _g(aid,"color",[])
        kwargs.update(x_cols=x, y_cols=color or None)

    elif aid == "correlation":
        x = _g(aid,"x", num) or num
        y = _g(aid,"y",[])
        kwargs.update(x_cols=x, y_cols=y or None)

    elif aid in ("categorical","pie_chart"):
        x        = _g(aid,"x", cat[:2]) or cat[:2]
        y        = _g(aid,"y",[]) or None
        agg      = _AGG_FUNCS.get(_g(aid,"agg","Mean (Avg)"),"mean")
        raw_sort = _g(aid,"sort","Value ↓")
        sort_by  = _sort_map.get(raw_sort, "Value (Desc)")
        top_n_v  = int(_g(aid,"top_n", 0) or 0)
        top_n    = top_n_v if top_n_v > 0 else None
        kwargs.update(x_cols=x, y_cols=y, agg=agg, sort_by=sort_by, top_n=top_n)
        if aid == "categorical":
            direction = _g(aid,"direction","Vertical (Column chart)")
            raw_dual  = _g(aid,"dual_y", NONE)
            dual_y    = None if (not raw_dual or raw_dual == NONE) else raw_dual
            # Ensure primary and secondary don't clash
            if dual_y and y and dual_y in (y if isinstance(y,list) else [y]):
                dual_y = None
            kwargs.update(direction=direction, dual_y_col=dual_y)

    elif aid == "time_series":
        x         = _g(aid,"x",[])
        y         = _g(aid,"y", num[:2]) or num[:2]
        agg       = _AGG_FUNCS.get(_g(aid,"agg","Mean (Avg)"),"mean")
        date_part = _DATE_PARTS.get(_g(aid,"date_part","None"))
        raw_dual  = _g(aid,"dual_y_ts", NONE)
        dual_y    = None if (not raw_dual or raw_dual == NONE) else raw_dual
        # Ensure secondary isn't same as any primary
        if dual_y and dual_y in (y if isinstance(y,list) else [y]):
            dual_y = None
        kwargs.update(x_cols=x or None, y_cols=y, agg=agg,
                      date_part=date_part, dual_y_col=dual_y)

    elif aid == "outlier":
        x = _g(aid,"x", num[:4]) or num[:4]
        g = _g(aid,"grp",[])
        kwargs.update(x_cols=x, y_cols=g or None)

    return kwargs


def _run(aid, df, **kwargs):
    fn = _RUNNERS.get(aid)
    if not fn:
        return []
    try:
        raw = fn(df) if aid in ("descriptive","data_quality") else fn(df, **kwargs)
        return [(str(uuid.uuid4())[:8], title, fig) for title, fig in raw]
    except Exception as e:
        st.error(f"Analysis error ({aid}): {e}")
        return None
