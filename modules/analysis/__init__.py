"""
modules/analysis/__init__.py -- Analysis registry & configuration layer.
This file is the single source of truth for every analysis type in Lytrize.
It owns three things:
  ANALYSIS_OPTIONS  -- the list of analysis cards shown on the analysis page.
                       Order here = order rendered in the UI.
  _RUNNERS          -- maps each analysis ID → its runner function.
                       The runner is called when the user clicks "Generate Charts".
  render_config_panel / _collect_kwargs -- the configuration UI layer.
    render_config_panel() draws the settings widgets.
    _collect_kwargs()     reads them back and builds the kwargs dict for the runner.
"""
import uuid
import streamlit as st

# ── Individual runner imports ─────────────────────────────────────────────────
from modules.analysis.descriptive  import run_descriptive
from modules.analysis.statistical  import run_statistical
from modules.analysis.distribution import run_distribution
from modules.analysis.correlation  import run_correlation
from modules.analysis.categorical  import run_categorical
from modules.analysis.pie_chart    import run_pie_chart
from modules.analysis.time_series  import run_time_series
from modules.analysis.outlier      import run_outlier, OUTLIER_HELP
from modules.analysis.scatter_plot import run_scatter_plot
from modules.analysis.map_plot     import run_map_plot
from modules.analysis.matrix_table import run_matrix_table

from modules.charts import PALETTES, num_cols as _num_cols, cat_cols as _cat_cols, dt_cols as _dt_cols

# ── Analysis registry ─────────────────────────────────────────────────────────
ANALYSIS_OPTIONS = [
    {"id": "descriptive",   "icon": "🗂️", "name": "Descriptive",       "desc": "Stats table -- numeric cols"},
    {"id": "statistical",   "icon": "📐", "name": "Statistical",        "desc": "Mean, std, min, max"},
    {"id": "distribution",  "icon": "📊", "name": "Distribution",       "desc": "Histograms & box plots"},
    {"id": "correlation",   "icon": "🔗", "name": "Correlation",        "desc": "Heatmap & scatter matrix"},
    {"id": "categorical",   "icon": "🏷️", "name": "Categorical Bar",    "desc": "Vertical & horizontal bars"},
    {"id": "pie_chart",     "icon": "🍩", "name": "Pie & Donut",        "desc": "Proportion & share analysis"},
    {"id": "time_series",   "icon": "⏱️", "name": "Time Series",        "desc": "Trends & time patterns"},
    {"id": "outlier",       "icon": "🚨", "name": "Outlier Detection",  "desc": "IQR-based anomaly analysis"},
    {"id": "scatter_plot",  "icon": "🔘", "name": "Scatter Plot",       "desc": "Relationship between 2 numeric vars"},
    {"id": "map_plot",      "icon": "🌍", "name": "Map Visualization",  "desc": "Geo scatter with lat/lon"},
    {"id": "matrix_table",  "icon": "📋", "name": "Matrix / Pivot Table","desc": "Cross-tabulation & heatmap"},
]

_RUNNERS = {
    "descriptive":  run_descriptive,
    "statistical":  run_statistical,
    "distribution": run_distribution,
    "correlation":  run_correlation,
    "categorical":  run_categorical,
    "pie_chart":    run_pie_chart,
    "time_series":  run_time_series,
    "outlier":      run_outlier,
    "scatter_plot": run_scatter_plot,
    "map_plot":     run_map_plot,
    "matrix_table": run_matrix_table,
}

_NEEDS_AXES = {
    "statistical", "distribution", "correlation", "categorical",
    "pie_chart", "time_series", "outlier", "scatter_plot", "map_plot", "matrix_table"
}
_NO_FORM = set()

_AGG_FUNCS = {
    "Mean (Avg)": "mean", "Sum": "sum", "Median": "median",
    "Count": "count", "Min": "min", "Max": "max"
}

_DATE_PARTS = {
    "None": None, "Year": "Y", "Quarter": "Q", "Month (number)": "M",
    "Month Name": "month_name", "Weekday Name": "weekday_name",
    "Day": "D", "Hour": "H"
}

# ── Session-state helpers ─────────────────────────────────────────────────────
def _sk(aid: str, key: str) -> str:
    return f"_cfg_{aid}_{key}"

def _g(aid: str, key: str, default=None):
    return st.session_state.get(_sk(aid, key), default)

def sk_uid(uid: str, aid: str, key: str) -> str:
    return f"edit{uid}_{aid}_{key}"

def _g_uid(uid: str, aid: str, key: str, default=None):
    return st.session_state.get(sk_uid(uid, aid, key), default)

# ── Configuration panel -- widget rendering ───────────────────────────────────
def render_config_panel(aid: str, df) -> None:
    num, cat, dt, all_cols = _num_cols(), _cat_cols(), _dt_cols(), df.columns.tolist()
    NONE = "None"
    st.selectbox("🎨 Colour Palette", list(PALETTES.keys()), key=_sk(aid, "palette"))
    st.markdown("---")

    if aid == "descriptive":
        st.info("No configuration needed -- outputs a full stats table.")

    elif aid == "statistical":
        c1, c2, c3 = st.columns(3)
        with c1: st.multiselect("Group by (optional)", cat, max_selections=1, key=_sk(aid, "x"))
        with c2: st.multiselect("Metrics", num, default=num[:4], key=_sk(aid, "y"))
        with c3: st.selectbox("Aggregation", list(_AGG_FUNCS.keys()), key=_sk(aid, "agg"))

    elif aid == "distribution":
        c1, c2 = st.columns(2)
        with c1: st.multiselect("Numeric columns", num, default=num[:4], key=_sk(aid, "x"))
        with c2: st.multiselect("Colour by (optional)", cat, max_selections=1, key=_sk(aid, "color"))

    elif aid == "correlation":
        c1, c2 = st.columns(2)
        with c1: st.multiselect("Columns", num, default=num, key=_sk(aid, "x"))
        with c2: st.multiselect("Additional (optional)", num, key=_sk(aid, "y"))

    elif aid in ("categorical", "pie_chart"):
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.multiselect("Dimension columns", cat, default=cat[:2], key=_sk(aid, "x"))
        with c2: st.multiselect("Metric columns (optional)", num, key=_sk(aid, "y"))
        with c3: st.selectbox("Aggregation", list(_AGG_FUNCS.keys()), key=_sk(aid, "agg"))
        with c4: st.selectbox("Sort", ["Value ↓", "Value ↑", "Category A→Z", "Category Z→A"], key=_sk(aid, "sort"))
        st.markdown("---")
        if aid == "categorical":
            st.selectbox("📊 Chart Direction", ["Vertical (Column chart)", "Horizontal (Bar chart)"], key=_sk(aid, "direction"))
        st.markdown("**🔝 Top N Categories**")
        st.caption("Enter how many top categories to show. Set to 0 to show all categories.")
        st.number_input("Top N (0 = show all)", min_value=0, max_value=200, step=1, value=0, key=_sk(aid, "top_n"))
        if aid == "categorical":
            st.markdown("---")
            st.markdown("**📊 Dual Y-Axis (Secondary metric as line overlay)**")
            dual_opts = [NONE] + list(num)
            st.selectbox("Secondary Y-Axis metric", dual_opts, key=_sk(aid, "dual_y"))
            st.selectbox("Secondary Aggregation", list(_AGG_FUNCS.keys()), key=_sk(aid, "dual_y_agg"),
                         help="Aggregation applied to the secondary metric independently from the primary.")

    elif aid == "time_series":
        dt_candidates = dt if dt else all_cols
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.multiselect("Date / Time column", dt_candidates, default=dt_candidates[:1] if dt_candidates else [], max_selections=1, key=_sk(aid, "x"))
        with c2: st.multiselect("Primary metric(s)", num, default=num[:2], key=_sk(aid, "y"))
        with c3: st.selectbox("Date grouping", list(_DATE_PARTS.keys()), key=_sk(aid, "date_part"))
        with c4: st.selectbox("Aggregation", list(_AGG_FUNCS.keys()), key=_sk(aid, "agg"))
        st.markdown("---")
        dual_opts_ts = [NONE] + list(num)
        st.selectbox("Secondary Y-Axis metric", dual_opts_ts, key=_sk(aid, "dual_y_ts"))
        st.selectbox("Secondary Aggregation", list(_AGG_FUNCS.keys()), key=_sk(aid, "dual_y_agg_ts"),
                     help="Aggregation applied to the secondary metric independently from the primary.")

    elif aid == "outlier":
        c1, c2 = st.columns(2)
        with c1: st.multiselect("Columns to analyse", num, default=num[:4], key=_sk(aid, "x"))
        with c2: st.multiselect("Group by (optional)", cat, max_selections=1, key=_sk(aid, "grp"))

    elif aid == "scatter_plot":
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.selectbox("📐 X-Axis (Independent)", num, key=_sk(aid, "x"))
        with c2: st.selectbox("📈 Y-Axis (Dependent)", num, index=1 if len(num)>1 else 0, key=_sk(aid, "y"))
        with c3: st.selectbox("🎨 Colour By", [NONE] + cat + num, key=_sk(aid, "color"))
        with c4: st.selectbox("📏 Size By", [NONE] + num, key=_sk(aid, "size"))
        st.selectbox("📉 Trendline", ["None", "OLS", "LOWESS"], key=_sk(aid, "trendline"))

    elif aid == "map_plot":
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.selectbox("📍 Latitude", num, key=_sk(aid, "lat"))
        with c2: st.selectbox("📍 Longitude", num, index=1 if len(num)>1 else 0, key=_sk(aid, "lon"))
        with c3: st.selectbox("📊 Metric (Size)", num, key=_sk(aid, "size"))
        with c4: st.selectbox("🎨 Colour By", [NONE] + cat + num, key=_sk(aid, "color"))
        st.selectbox("🏷️ Hover Label", [NONE] + all_cols, key=_sk(aid, "location"))

    elif aid == "matrix_table":
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.selectbox("📑 Index (Rows)", cat + num, key=_sk(aid, "idx"))
        with c2: st.selectbox("📑 Columns", cat + num, key=_sk(aid, "cols"))
        with c3: st.selectbox("📊 Values", num, key=_sk(aid, "vals"))
        with c4: st.selectbox("⚙️ Aggregation", list(_AGG_FUNCS.keys()), key=_sk(aid, "agg"))
        st.selectbox("🖼️ Render As", ["Heatmap", "Table"], key=_sk(aid, "view"))

# ── Configuration collection ──────────────────────────────────────────────────
def _collect_kwargs(aid: str, df) -> dict:
    num, cat, dt, all_cols = _num_cols(), _cat_cols(), _dt_cols(), df.columns.tolist()
    NONE = "None"
    pal_label = _g(aid, "palette", list(PALETTES.keys())[0])
    palette = PALETTES.get(pal_label, list(PALETTES.values())[0])
    kwargs = {"palette": palette}

    _sort_map = {
        "Value ↓": "Value (Desc)", "Value ↑": "Value (Asc)",
        "Category A→Z": "Category (A-Z)", "Category Z→A": "Category (Z-A)"
    }

    if aid == "statistical":
        kwargs.update(x_cols=_g(aid, "x", []) or None, y_cols=_g(aid, "y", num[:4]) or num,
                      agg=_AGG_FUNCS.get(_g(aid, "agg", "Mean (Avg)"), "mean"))
    elif aid == "distribution":
        kwargs.update(x_cols=_g(aid, "x", num[:4]) or num[:4], y_cols=_g(aid, "color", []) or None)
    elif aid == "correlation":
        kwargs.update(x_cols=_g(aid, "x", num) or num, y_cols=_g(aid, "y", []) or None)
    elif aid in ("categorical", "pie_chart"):
        x = _g(aid, "x", cat[:2]) or cat[:2]
        y = _g(aid, "y", []) or None
        agg = _AGG_FUNCS.get(_g(aid, "agg", "Mean (Avg)"), "mean")
        top_n_v = int(_g(aid, "top_n", 0) or 0)
        top_n = top_n_v if top_n_v > 0 else None
        sort_by = _sort_map.get(_g(aid, "sort", "Value ↓"), "Value (Desc)")
        kwargs.update(x_cols=x, y_cols=y, agg=agg, sort_by=sort_by, top_n=top_n)
        if aid == "categorical":
            direction = _g(aid, "direction", "Vertical (Column chart)")
            raw_dual = _g(aid, "dual_y", NONE)
            dual_y = None if (not raw_dual or raw_dual == NONE) else raw_dual
            if dual_y and y and dual_y in (y if isinstance(y, list) else [y]): dual_y = None
            dual_y_agg = _AGG_FUNCS.get(_g(aid, "dual_y_agg", "Mean (Avg)"), "mean")
            kwargs.update(direction=direction, dual_y_col=dual_y, dual_y_agg=dual_y_agg)
    elif aid == "time_series":
        x = _g(aid, "x", [])
        y = _g(aid, "y", num[:2]) or num[:2]
        agg = _AGG_FUNCS.get(_g(aid, "agg", "Mean (Avg)"), "mean")
        date_part = _DATE_PARTS.get(_g(aid, "date_part", "None"))
        raw_dual = _g(aid, "dual_y_ts", NONE)
        dual_y = None if (not raw_dual or raw_dual == NONE) else raw_dual
        if dual_y and dual_y in (y if isinstance(y, list) else [y]): dual_y = None
        dual_y_agg = _AGG_FUNCS.get(_g(aid, "dual_y_agg_ts", "Mean (Avg)"), "mean")
        kwargs.update(x_cols=x or None, y_cols=y, agg=agg, date_part=date_part, dual_y_col=dual_y, dual_y_agg=dual_y_agg)
    elif aid == "outlier":
        kwargs.update(x_cols=_g(aid, "x", num[:4]) or num[:4], y_cols=_g(aid, "grp", []) or None)
    elif aid == "scatter_plot":
        kwargs.update(x_col=_g(aid, "x", num[0]), y_col=_g(aid, "y", num[1] if len(num)>1 else num[0]),
                      color_col=_g(aid, "color", NONE), size_col=_g(aid, "size", NONE),
                      trendline=_g(aid, "trendline", "None"))
    elif aid == "map_plot":
        kwargs.update(lat_col=_g(aid, "lat", num[0]), lon_col=_g(aid, "lon", num[1] if len(num)>1 else num[0]),
                      size_col=_g(aid, "size", NONE), color_col=_g(aid, "color", NONE),
                      location_col=_g(aid, "location", NONE))
    elif aid == "matrix_table":
        kwargs.update(index_col=_g(aid, "idx", cat[0] if cat else df.columns[0]),
                      columns_col=_g(aid, "cols", cat[1] if len(cat)>1 else df.columns[1]),
                      values_col=_g(aid, "vals", num[0] if num else None),
                      agg=_AGG_FUNCS.get(_g(aid, "agg", "Mean (Avg)"), "mean"),
                      view_type=_g(aid, "view", "Heatmap"))
    return kwargs

# ── Scoped versions (for chart regeneration panels) ──────────────────────────
def render_config_panel_scoped(uid: str, aid: str, df) -> None:
    num, cat, dt, all_cols = _num_cols(), _cat_cols(), _dt_cols(), df.columns.tolist()
    NONE = "None"
    sk = lambda key: sk_uid(uid, aid, key)
    st.selectbox("🎨 Colour Palette", list(PALETTES.keys()), key=sk("palette"))
    st.markdown("---")

    if aid == "statistical":
        c1, c2, c3 = st.columns(3)
        with c1: st.multiselect("Group by (optional)", cat, max_selections=1, key=sk("x"))
        with c2: st.multiselect("Metrics", num, default=num[:4], key=sk("y"))
        with c3: st.selectbox("Aggregation", list(_AGG_FUNCS.keys()), key=sk("agg"))
    elif aid == "distribution":
        c1, c2 = st.columns(2)
        with c1: st.multiselect("Numeric columns", num, default=num[:4], key=sk("x"))
        with c2: st.multiselect("Colour by (optional)", cat, max_selections=1, key=sk("color"))
    elif aid == "correlation":
        c1, c2 = st.columns(2)
        with c1: st.multiselect("Columns", num, default=num, key=sk("x"))
        with c2: st.multiselect("Additional (optional)", num, key=sk("y"))
    elif aid in ("categorical", "pie_chart"):
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.multiselect("Dimension columns", cat, default=cat[:2], key=sk("x"))
        with c2: st.multiselect("Metric columns (optional)", num, key=sk("y"))
        with c3: st.selectbox("Aggregation", list(_AGG_FUNCS.keys()), key=sk("agg"))
        with c4: st.selectbox("Sort", ["Value ↓", "Value ↑", "Category A→Z", "Category Z→A"], key=sk("sort"))
        st.markdown("---")
        if aid == "categorical": st.selectbox("📊 Chart Direction", ["Vertical", "Horizontal"], key=sk("direction"))
        st.markdown("**🔝 Top N Categories**")
        st.number_input("Top N", min_value=0, max_value=200, step=1, value=0, key=sk("top_n"))
        if aid == "categorical":
            st.markdown("---")
            st.selectbox("Secondary Y-Axis", [NONE] + num, key=sk("dual_y"))
            st.selectbox("Secondary Aggregation", list(_AGG_FUNCS.keys()), key=sk("dual_y_agg"))
    elif aid == "time_series":
        dt_candidates = dt if dt else all_cols
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.multiselect("Date / Time column", dt_candidates, default=dt_candidates[:1] if dt_candidates else [], max_selections=1, key=sk("x"))
        with c2: st.multiselect("Primary metric(s)", num, default=num[:2], key=sk("y"))
        with c3: st.selectbox("Date grouping", list(_DATE_PARTS.keys()), key=sk("date_part"))
        with c4: st.selectbox("Aggregation", list(_AGG_FUNCS.keys()), key=sk("agg"))
        st.markdown("---")
        st.selectbox("Secondary Y-Axis", [NONE] + num, key=sk("dual_y_ts"))
        st.selectbox("Secondary Aggregation", list(_AGG_FUNCS.keys()), key=sk("dual_y_agg_ts"))
    elif aid == "outlier":
        c1, c2 = st.columns(2)
        with c1: st.multiselect("Columns to analyse", num, default=num[:4], key=sk("x"))
        with c2: st.multiselect("Group by (optional)", cat, max_selections=1, key=sk("grp"))
    elif aid == "scatter_plot":
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.selectbox("📐 X-Axis", num, key=sk("x"))
        with c2: st.selectbox("📈 Y-Axis", num, index=1 if len(num)>1 else 0, key=sk("y"))
        with c3: st.selectbox("🎨 Colour By", [NONE] + cat + num, key=sk("color"))
        with c4: st.selectbox("📏 Size By", [NONE] + num, key=sk("size"))
        st.selectbox("📉 Trendline", ["None", "OLS", "LOWESS"], key=sk("trendline"))
    elif aid == "map_plot":
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.selectbox("📍 Latitude", num, key=sk("lat"))
        with c2: st.selectbox("📍 Longitude", num, index=1 if len(num)>1 else 0, key=sk("lon"))
        with c3: st.selectbox("📊 Metric (Size)", num, key=sk("size"))
        with c4: st.selectbox("🎨 Colour By", [NONE] + cat + num, key=sk("color"))
        st.selectbox("🏷️ Hover Label", [NONE] + all_cols, key=sk("location"))
    elif aid == "matrix_table":
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.selectbox("📑 Index", cat + num, key=sk("idx"))
        with c2: st.selectbox("📑 Columns", cat + num, key=sk("cols"))
        with c3: st.selectbox("📊 Values", num, key=sk("vals"))
        with c4: st.selectbox("⚙️ Aggregation", list(_AGG_FUNCS.keys()), key=sk("agg"))
        st.selectbox("🖼️ Render As", ["Heatmap", "Table"], key=sk("view"))

def _collect_kwargs_scoped(uid: str, aid: str, df) -> dict:
    num, cat, dt, all_cols = _num_cols(), _cat_cols(), _dt_cols(), df.columns.tolist()
    NONE = "None"
    g = lambda key, default=None: _g_uid(uid, aid, key, default)
    _sort_map = {"Value ↓": "Value (Desc)", "Value ↑": "Value (Asc)", "Category A→Z": "Category (A-Z)", "Category Z→A": "Category (Z-A)"}
    pal_label = g("palette", list(PALETTES.keys())[0])
    kwargs = {"palette": PALETTES.get(pal_label, list(PALETTES.values())[0])}

    if aid == "statistical":
        kwargs.update(x_cols=g("x",[]) or None, y_cols=g("y",num[:4]) or num, agg=_AGG_FUNCS.get(g("agg", "Mean (Avg)"), "mean"))
    elif aid == "distribution":
        kwargs.update(x_cols=g("x",num[:4]) or num[:4], y_cols=g("color",[]) or None)
    elif aid == "correlation":
        kwargs.update(x_cols=g("x",num) or num, y_cols=g("y",[]) or None)
    elif aid in ("categorical", "pie_chart"):
        x = g("x", cat[:2]) or cat[:2]
        y = g("y", []) or None
        kwargs.update(x_cols=x, y_cols=y,
                      agg=_AGG_FUNCS.get(g("agg", "Mean (Avg)"), "mean"),
                      sort_by=_sort_map.get(g("sort", "Value ↓"), "Value (Desc)"),
                      top_n=g("top_n", 0) or None)
        if aid == "categorical":
            direction = g("direction", "Vertical (Column chart)")
            raw_dual = g("dual_y", NONE)
            dual_y = None if (not raw_dual or raw_dual == NONE) else raw_dual
            if dual_y and y and dual_y in (y if isinstance(y, list) else [y]):
                dual_y = None
            dual_y_agg = _AGG_FUNCS.get(g("dual_y_agg", "Mean (Avg)"), "mean")
            kwargs.update(direction=direction, dual_y_col=dual_y, dual_y_agg=dual_y_agg)
    elif aid == "time_series":
        x = g("x", [])
        y = g("y", num[:2]) or num[:2]
        agg = _AGG_FUNCS.get(g("agg", "Mean (Avg)"), "mean")
        date_part = _DATE_PARTS.get(g("date_part", "None"))
        raw_dual = g("dual_y_ts", NONE)
        dual_y = None if (not raw_dual or raw_dual == NONE) else raw_dual
        if dual_y and dual_y in (y if isinstance(y, list) else [y]):
            dual_y = None
        dual_y_agg = _AGG_FUNCS.get(g("dual_y_agg_ts", "Mean (Avg)"), "mean")
        kwargs.update(x_cols=x or None, y_cols=y, agg=agg,
                      date_part=date_part, dual_y_col=dual_y, dual_y_agg=dual_y_agg)
    elif aid == "outlier":
        kwargs.update(x_cols=g("x",num[:4]) or num[:4], y_cols=g("grp",[]) or None)
    elif aid == "scatter_plot":
        kwargs.update(x_col=g("x", num[0]), y_col=g("y", num[1] if len(num)>1 else num[0]),
                      color_col=g("color", NONE), size_col=g("size", NONE), trendline=g("trendline", "None"))
    elif aid == "map_plot":
        kwargs.update(lat_col=g("lat", num[0]), lon_col=g("lon", num[1] if len(num)>1 else num[0]),
                      size_col=g("size", NONE), color_col=g("color", NONE), location_col=g("location", NONE))
    elif aid == "matrix_table":
        kwargs.update(index_col=g("idx", cat[0] if cat else df.columns[0]),
                      columns_col=g("cols", cat[1] if len(cat)>1 else df.columns[1]),
                      values_col=g("vals", num[0] if num else None),
                      agg=_AGG_FUNCS.get(g("agg", "Mean (Avg)"), "mean"),
                      view_type=g("view", "Heatmap"))
    return kwargs

# ── Runner dispatcher ─────────────────────────────────────────────────────────
def _run(aid: str, df, **kwargs):
    fn = _RUNNERS.get(aid)
    if not fn: return []
    try:
        raw = fn(df) if aid in ("descriptive", "data_quality") else fn(df, **kwargs)
        return [(str(uuid.uuid4())[:8], title, fig) for title, fig in raw]
    except Exception as e:
        st.error(f"Analysis error ({aid}): {e}")
        return None