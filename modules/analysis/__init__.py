"""
modules/analysis/__init__.py -- Analysis registry & configuration layer.
========================================================================

This file is the single source of truth for every analysis type in Lytrize.
It owns three things:

  1. ANALYSIS_OPTIONS  -- the list of analysis cards shown on the analysis page.
                         Order here = order rendered in the UI.

  2. _RUNNERS          -- maps each analysis ID → its runner function.
                         The runner is called when the user clicks "Generate Charts".

  3. render_config_panel / _collect_kwargs -- the configuration UI layer.
     render_config_panel() draws the settings widgets.
     _collect_kwargs()     reads them back and builds the kwargs dict for the runner.

──────────────────────────────────────────────────────────────────────────────
HOW TO ADD A NEW ANALYSIS TYPE  (step-by-step for contributors)
──────────────────────────────────────────────────────────────────────────────

Step 1 -- Create the runner file:
    modules/analysis/my_analysis.py

    The runner must be a function with this signature:
        def run_my_analysis(df, **kwargs) -> list[tuple[str, Figure]]:
            ...
            return [(chart_title, plotly_figure), ...]

    Each tuple becomes one chart card on the analysis page.
    Return an empty list [] if nothing can be plotted (e.g. missing columns).

Step 2 -- Register it in ANALYSIS_OPTIONS (this file, ~line 60):
    {
        "id":   "my_analysis",      # unique slug -- used as the key everywhere
        "icon": "🧩",               # emoji shown on the card
        "name": "My Analysis",      # display name
        "desc": "Short description" # subtitle on the card
    }

Step 3 -- Add it to _RUNNERS (this file, ~line 80):
    "my_analysis": run_my_analysis,

Step 4 -- Add configuration widgets in render_config_panel() (~line 120):
    elif aid == "my_analysis":
        st.multiselect("Columns", num, key=_sk(aid, "cols"))

Step 5 -- Read those widgets in _collect_kwargs() (~line 200):
    elif aid == "my_analysis":
        kwargs.update(cols=_g(aid, "cols", []) or num)

That's it. The analysis page will automatically show your card, call your
configuration widgets, and invoke your runner with the collected kwargs.

──────────────────────────────────────────────────────────────────────────────
SPECIAL ANALYSIS IDS  (need extra handling in pages/analysis.py)
──────────────────────────────────────────────────────────────────────────────
  "data_quality" → listed in _NO_FORM:   rendered without the config form.
  "descriptive"  → custom code path:     renders a table inline, no chart output.

All other IDs follow the standard two-step flow:
    configure (render_config_panel) → generate (_run → _RUNNERS[aid])
"""

import uuid
import streamlit as st

# ── Individual runner imports ─────────────────────────────────────────────────
# Each module lives in modules/analysis/<name>.py
from modules.analysis.descriptive  import run_descriptive
from modules.analysis.statistical  import run_statistical
from modules.analysis.distribution import run_distribution
from modules.analysis.correlation  import run_correlation
from modules.analysis.categorical  import run_categorical
from modules.analysis.pie_chart    import run_pie_chart
from modules.analysis.time_series  import run_time_series
from modules.analysis.data_quality import run_data_quality
from modules.analysis.outlier      import run_outlier, OUTLIER_HELP

# Column-list helpers -- read from session_state (set during upload/classify)
from modules.charts import PALETTES, num_cols as _num_cols, cat_cols as _cat_cols, dt_cols as _dt_cols


# ─────────────────────────────────────────────────────────────────────────────
# Analysis registry
# ─────────────────────────────────────────────────────────────────────────────

# ANALYSIS_OPTIONS drives the card grid on the analysis page.
# To add a new analysis: append a dict here AND add an entry to _RUNNERS below.
ANALYSIS_OPTIONS = [
    {"id": "descriptive",  "icon": "🗂️", "name": "Descriptive",      "desc": "Stats table -- numeric cols"},
    {"id": "data_quality", "icon": "🧹", "name": "Data Quality",      "desc": "Missing values & duplicates"},
    {"id": "statistical",  "icon": "📐", "name": "Statistical",       "desc": "Mean, std, min, max"},
    {"id": "distribution", "icon": "📊", "name": "Distribution",      "desc": "Histograms & box plots"},
    {"id": "correlation",  "icon": "🔗", "name": "Correlation",       "desc": "Heatmap & scatter matrix"},
    {"id": "categorical",  "icon": "🏷️", "name": "Categorical Bar",   "desc": "Vertical & horizontal bars"},
    {"id": "pie_chart",    "icon": "🍩", "name": "Pie & Donut",       "desc": "Proportion & share analysis"},
    {"id": "time_series",  "icon": "⏱️", "name": "Time Series",       "desc": "Trends & time patterns"},
    {"id": "outlier",      "icon": "🚨", "name": "Outlier Detection", "desc": "IQR-based anomaly analysis"},
]

# _RUNNERS maps analysis ID → the function that produces (title, fig) tuples.
# Signature for every runner:  fn(df, **kwargs) -> list[tuple[str, Figure]]
# Exceptions: descriptive and data_quality take only df (no kwargs).
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

# Analyses that need axis/column selection via the config panel.
_NEEDS_AXES = {"statistical", "distribution", "correlation", "categorical",
               "pie_chart", "time_series", "outlier"}

# Analyses that must NOT be wrapped in an st.form() -- they contain their own
# st.button() widgets (data_quality has inline "Drop NA" / "Drop Duplicates").
_NO_FORM = {"data_quality"}

# ── Aggregation function labels → pandas method strings ───────────────────────
_AGG_FUNCS = {
    "Mean (Avg)": "mean",
    "Sum":        "sum",
    "Median":     "median",
    "Count":      "count",
    "Min":        "min",
    "Max":        "max",
}

# ── Date-part grouping labels → pandas period/alias strings ───────────────────
# None means "use the raw date column without any grouping".
_DATE_PARTS = {
    "None":           None,
    "Year":           "Y",
    "Quarter":        "Q",
    "Month (number)": "M",
    "Month Name":     "month_name",    # special-cased in time_series.py
    "Weekday Name":   "weekday_name",  # special-cased in time_series.py
    "Day":            "D",
    "Hour":           "H",
}


# ─────────────────────────────────────────────────────────────────────────────
# Session-state helpers
# ─────────────────────────────────────────────────────────────────────────────

def _sk(aid: str, key: str) -> str:
    """
    Build a namespaced session_state key for a widget inside analysis `aid`.

    Using a consistent naming scheme prevents key collisions between different
    analysis types sharing widget names like "x" or "palette".

    Example: _sk("categorical", "top_n")  →  "_cfg_categorical_top_n"
    """
    return f"_cfg_{aid}_{key}"


def _g(aid: str, key: str, default=None):
    """
    Read a widget value from session_state, falling back to `default`.

    Args:
        aid:     Analysis ID (e.g. "categorical").
        key:     Widget key suffix (e.g. "top_n").
        default: Value returned when the key is not yet in session_state.
    """
    return st.session_state.get(_sk(aid, key), default)


# ─────────────────────────────────────────────────────────────────────────────
# Configuration panel -- widget rendering
# ─────────────────────────────────────────────────────────────────────────────

def render_config_panel(aid: str, df) -> None:
    """
    Render configuration widgets for the analysis identified by `aid`.

    Design rules:
      - ALL widgets are ALWAYS visible -- no show/hide conditionals that react
        to other widget values during the same rerun. This avoids the Streamlit
        "missing key" crash caused by widgets appearing/disappearing mid-rerun.
      - Every widget uses _sk(aid, key) as its Streamlit key so values persist
        across reruns and are accessible via _collect_kwargs().
      - This function returns nothing; the caller reads config via _collect_kwargs().

    Args:
        aid: Analysis ID string (e.g. "categorical", "time_series").
        df:  The working DataFrame from st.session_state.df.
    """
    num, cat, dt, all_cols = _num_cols(), _cat_cols(), _dt_cols(), df.columns.tolist()
    NONE = "None"  # Sentinel string used in "no secondary column" selectboxes.

    # Colour palette selector -- shown for every analysis that has a config panel.
    st.selectbox("🎨 Colour Palette", list(PALETTES.keys()), key=_sk(aid, "palette"))
    st.markdown("---")

    # ── Descriptive ───────────────────────────────────────────────────────────
    # No configuration needed -- the runner outputs a full pandas describe() table.
    if aid == "descriptive":
        st.info("No configuration needed -- outputs a full stats table.")

    # ── Statistical ───────────────────────────────────────────────────────────
    # Aggregates numeric metrics, optionally grouped by one categorical column.
    elif aid == "statistical":
        c1, c2, c3 = st.columns(3)
        with c1: st.multiselect("Group by (optional)", cat, max_selections=1, key=_sk(aid, "x"))
        with c2: st.multiselect("Metrics", num, default=num[:4], key=_sk(aid, "y"))
        with c3: st.selectbox("Aggregation", list(_AGG_FUNCS.keys()), key=_sk(aid, "agg"))

    # ── Distribution ──────────────────────────────────────────────────────────
    # Histograms with box-plot marginals for each selected numeric column.
    elif aid == "distribution":
        c1, c2 = st.columns(2)
        with c1: st.multiselect("Numeric columns", num, default=num[:4], key=_sk(aid, "x"))
        with c2: st.multiselect("Colour by (optional)", cat, max_selections=1, key=_sk(aid, "color"))

    # ── Correlation ───────────────────────────────────────────────────────────
    # Pearson correlation heatmap. Requires at least 2 numeric columns.
    elif aid == "correlation":
        c1, c2 = st.columns(2)
        with c1: st.multiselect("Columns", num, default=num, key=_sk(aid, "x"))
        with c2: st.multiselect("Additional (optional)", num, key=_sk(aid, "y"))

    # ── Categorical Bar & Pie / Donut ─────────────────────────────────────────
    # Both share dimension / metric / aggregation / sort selectors.
    # Categorical adds direction (vertical/horizontal) and dual Y-axis.
    # Pie adds "Other" grouping for categories beyond Top N.
    elif aid in ("categorical", "pie_chart"):
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.multiselect("Dimension columns", cat, default=cat[:2], key=_sk(aid, "x"))
        with c2: st.multiselect("Metric columns (optional)", num, key=_sk(aid, "y"))
        with c3: st.selectbox("Aggregation", list(_AGG_FUNCS.keys()), key=_sk(aid, "agg"))
        with c4: st.selectbox(
            "Sort", ["Value ↓", "Value ↑", "Category A→Z", "Category Z→A"],
            key=_sk(aid, "sort"))
        st.markdown("---")

        # Categorical-only: chart orientation toggle.
        if aid == "categorical":
            st.selectbox(
                "📊 Chart Direction",
                ["Vertical (Column chart)", "Horizontal (Bar chart)"],
                key=_sk(aid, "direction"),
                help="Vertical = column chart. Horizontal = bar chart with values outside tips.")

        # Top-N -- always a number_input (0 = show all).
        # Using number_input instead of a conditional checkbox avoids key-missing crashes.
        st.markdown("**🔝 Top N Categories**")
        st.caption("Enter how many top categories to show. Set to 0 to show all categories.")
        st.number_input(
            "Top N (0 = show all)", min_value=0, max_value=200, step=1, value=0,
            key=_sk(aid, "top_n"),
            help="0 = no limit. e.g. 10 = show only the 10 highest-value categories.")

        # Dual Y-axis -- categorical only; selectbox with "None" sentinel.
        if aid == "categorical":
            st.markdown("---")
            st.markdown("**📊 Dual Y-Axis (Secondary metric as line overlay)**")
            st.caption("Choose a secondary metric to overlay as a line on a second Y-axis. Select 'None' to disable.")
            dual_opts = [NONE] + list(num)
            st.selectbox(
                "Secondary Y-Axis metric", dual_opts, key=_sk(aid, "dual_y"),
                help="Primary metric → bars. Secondary metric → line on the right Y-axis.")

    # ── Time Series ───────────────────────────────────────────────────────────
    # Line charts over time with optional date-part grouping and dual Y-axis.
    elif aid == "time_series":
        dt_candidates = dt if dt else all_cols
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.multiselect(
                "Date / Time column", dt_candidates,
                default=dt_candidates[:1] if dt_candidates else [],
                max_selections=1, key=_sk(aid, "x"))
        with c2: st.multiselect("Primary metric(s)", num, default=num[:2], key=_sk(aid, "y"))
        with c3: st.selectbox("Date grouping", list(_DATE_PARTS.keys()), key=_sk(aid, "date_part"))
        with c4: st.selectbox("Aggregation", list(_AGG_FUNCS.keys()), key=_sk(aid, "agg"))
        st.markdown("---")

        # Dual Y -- always-visible selectbox with "None" sentinel (see note above).
        st.markdown("**📊 Dual Y-Axis (Secondary metric as dashed line)**")
        st.caption("Choose a secondary metric on the right Y-axis. Select 'None' to disable.")
        dual_opts_ts = [NONE] + list(num)
        st.selectbox(
            "Secondary Y-Axis metric", dual_opts_ts, key=_sk(aid, "dual_y_ts"),
            help="Adds a second line on the right axis.")

    # ── Outlier Detection ─────────────────────────────────────────────────────
    # IQR-based scatter plots flagging values outside 1.5×IQR boundaries.
    elif aid == "outlier":
        c1, c2 = st.columns(2)
        with c1: st.multiselect("Columns to analyse", num, default=num[:4], key=_sk(aid, "x"))
        with c2: st.multiselect("Group by (optional)", cat, max_selections=1, key=_sk(aid, "grp"))


# ─────────────────────────────────────────────────────────────────────────────
# Configuration collection -- reading widget values → kwargs dict
# ─────────────────────────────────────────────────────────────────────────────

def _collect_kwargs(aid: str, df) -> dict:
    """
    Read widget values from session_state and return a kwargs dict for the runner.

    Called immediately before _run() to translate the user's configuration
    choices into typed Python arguments understood by each analysis runner.

    Args:
        aid: Analysis ID (e.g. "categorical").
        df:  The working DataFrame (used to infer defaults when selection is empty).

    Returns:
        dict of keyword arguments passed to the runner via **kwargs.
    """
    num, cat, dt, all_cols = _num_cols(), _cat_cols(), _dt_cols(), df.columns.tolist()
    NONE = "None"

    # Resolve palette -- always present because the selectbox is shown for all analyses.
    pal_label = _g(aid, "palette", list(PALETTES.keys())[0])
    palette   = PALETTES.get(pal_label, list(PALETTES.values())[0])
    kwargs    = {"palette": palette}

    # Sort label → internal sort key used by categorical / pie runners.
    _sort_map = {
        "Value ↓":       "Value (Desc)",
        "Value ↑":       "Value (Asc)",
        "Category A→Z":  "Category (A-Z)",
        "Category Z→A":  "Category (Z-A)",
    }

    # ── Statistical ───────────────────────────────────────────────────────────
    if aid == "statistical":
        x   = _g(aid, "x", [])
        y   = _g(aid, "y", num[:4]) or num
        agg = _AGG_FUNCS.get(_g(aid, "agg", "Mean (Avg)"), "mean")
        kwargs.update(x_cols=x or None, y_cols=y, agg=agg)

    # ── Distribution ──────────────────────────────────────────────────────────
    elif aid == "distribution":
        x     = _g(aid, "x", num[:4]) or num[:4]
        color = _g(aid, "color", [])
        kwargs.update(x_cols=x, y_cols=color or None)

    # ── Correlation ───────────────────────────────────────────────────────────
    elif aid == "correlation":
        x = _g(aid, "x", num) or num
        y = _g(aid, "y", [])
        kwargs.update(x_cols=x, y_cols=y or None)

    # ── Categorical & Pie ─────────────────────────────────────────────────────
    elif aid in ("categorical", "pie_chart"):
        x        = _g(aid, "x", cat[:2]) or cat[:2]
        y        = _g(aid, "y", []) or None
        agg      = _AGG_FUNCS.get(_g(aid, "agg", "Mean (Avg)"), "mean")
        raw_sort = _g(aid, "sort", "Value ↓")
        sort_by  = _sort_map.get(raw_sort, "Value (Desc)")
        top_n_v  = int(_g(aid, "top_n", 0) or 0)
        top_n    = top_n_v if top_n_v > 0 else None  # 0 → None means "show all"
        kwargs.update(x_cols=x, y_cols=y, agg=agg, sort_by=sort_by, top_n=top_n)

        if aid == "categorical":
            direction = _g(aid, "direction", "Vertical (Column chart)")
            raw_dual  = _g(aid, "dual_y", NONE)
            dual_y    = None if (not raw_dual or raw_dual == NONE) else raw_dual
            # Prevent the secondary metric from being the same as the primary.
            if dual_y and y and dual_y in (y if isinstance(y, list) else [y]):
                dual_y = None
            kwargs.update(direction=direction, dual_y_col=dual_y)

    # ── Time Series ───────────────────────────────────────────────────────────
    elif aid == "time_series":
        x         = _g(aid, "x", [])
        y         = _g(aid, "y", num[:2]) or num[:2]
        agg       = _AGG_FUNCS.get(_g(aid, "agg", "Mean (Avg)"), "mean")
        date_part = _DATE_PARTS.get(_g(aid, "date_part", "None"))
        raw_dual  = _g(aid, "dual_y_ts", NONE)
        dual_y    = None if (not raw_dual or raw_dual == NONE) else raw_dual
        # Prevent secondary from being the same column as any primary metric.
        if dual_y and dual_y in (y if isinstance(y, list) else [y]):
            dual_y = None
        kwargs.update(x_cols=x or None, y_cols=y, agg=agg,
                      date_part=date_part, dual_y_col=dual_y)

    # ── Outlier ───────────────────────────────────────────────────────────────
    elif aid == "outlier":
        x = _g(aid, "x", num[:4]) or num[:4]
        g = _g(aid, "grp", [])
        kwargs.update(x_cols=x, y_cols=g or None)

    return kwargs


# ─────────────────────────────────────────────────────────────────────────────
# Runner dispatcher
# ─────────────────────────────────────────────────────────────────────────────

def _run(aid: str, df, **kwargs):
    """
    Dispatch to the correct runner and return a list of (uid, title, fig) tuples.

    Args:
        aid:    Analysis ID (must be a key in _RUNNERS).
        df:     The working DataFrame.
        **kwargs: Collected from _collect_kwargs(); forwarded to the runner.

    Returns:
        list of (uid: str, title: str, fig: Figure) ready to append to charts.
        Returns None if the runner raises an error (caller shows st.error).

    Notes:
        - descriptive and data_quality runners only accept df (no kwargs).
          All others receive **kwargs.
        - UIDs are 8-character hex strings; short enough to be readable in
          session_state keys but unique enough for typical session sizes.
    """
    fn = _RUNNERS.get(aid)
    if not fn:
        return []
    try:
        # Analyses that render inline (no kwargs) vs. chart-producing analyses.
        raw = fn(df) if aid in ("descriptive", "data_quality") else fn(df, **kwargs)
        # Wrap each (title, fig) tuple with a fresh unique ID.
        return [(str(uuid.uuid4())[:8], title, fig) for title, fig in raw]
    except Exception as e:
        st.error(f"Analysis error ({aid}): {e}")
        return None
