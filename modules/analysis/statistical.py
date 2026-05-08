"""
modules/analysis/statistical.py -- Statistical aggregation chart runner.
=======================================================================

Produces aggregated bar charts summarising numeric columns using a chosen
aggregation function (mean, sum, median, count, min, max).

Two operating modes depending on whether a group-by column is selected:

  Grouped mode:   One bar chart per metric, bars split by the categorical
                  group-by column. Useful for comparing averages across
                  departments, regions, product lines, etc.

  Overview mode:  A single bar chart showing the aggregated value for every
                  numeric column side by side, plus a companion standard
                  deviation chart. Useful for a quick "how do the numbers
                  compare?" across all metrics.
"""

import streamlit as st
import plotly.express as px
from modules.charts import chart_layout, COLORS, num_cols as _num_cols


@st.cache_data(show_spinner=False)
def _agg_grouped(df, grp: str, metric: str, agg: str):
    """Cached groupby aggregation -- recomputed only when df or params change."""
    result = df.groupby(grp)[metric].agg(agg).reset_index()
    result.columns = [grp, f"{agg.title()} {metric}"]
    return result


@st.cache_data(show_spinner=False)
def _agg_overview(df, num: tuple, agg: str):
    """Cached overview aggregation across all numeric columns."""
    cols = list(num)
    summary = df[cols].agg(agg).reset_index()
    summary.columns = ["Column", agg.title()]
    stds = df[cols].std().reset_index()
    stds.columns = ["Column", "Std Dev"]
    return summary, stds


def run_statistical(df, x_cols=None, y_cols=None, agg="mean", palette=None, **kwargs):
    """
    Generate statistical aggregation bar charts.

    Args:
        df:      Working DataFrame.
        x_cols:  List containing one categorical column to group by (optional).
                 If empty or None, overview mode is used.
        y_cols:  Numeric columns to aggregate. Defaults to all numeric cols.
        agg:     Aggregation function: "mean", "sum", "median", "count", "min", "max".
        palette: List of hex colour strings.
        **kwargs: Extra kwargs silently ignored.

    Returns:
        list of (title: str, fig: Figure) tuples.
        Grouped mode   → one chart per metric in y_cols.
        Overview mode  → two charts: aggregated overview + std dev.
    """
    charts    = []
    num       = y_cols or _num_cols()
    grp       = x_cols[0] if x_cols else None  # Only one group-by column supported.
    agg_label = agg.title()
    pal       = palette or COLORS

    if grp and grp in df.columns:
        # ── Grouped mode -- one chart per metric (cached aggregation) ──────────
        for metric in num:
            agg_vals = _agg_grouped(df, grp, metric, agg)
            fig = px.bar(
                agg_vals, x=grp, y=f"{agg_label} {metric}",
                title=f"{agg_label} of {metric} by {grp}",
                color=grp, color_discrete_sequence=pal, text_auto=".2f")
            fig.update_layout(**chart_layout())
            charts.append((f"{agg_label} by {grp}", fig))

    else:
        # ── Overview mode -- all metrics in one chart (cached aggregation) ─────
        summary, stds = _agg_overview(df, tuple(num), agg)
        summary.columns = ["Column", agg_label]
        fig = px.bar(
            summary, x="Column", y=agg_label,
            title=f"{agg_label} Overview",
            color="Column", color_discrete_sequence=pal, text_auto=".2f")
        fig.update_layout(**chart_layout())
        charts.append((f"{agg_label} Values", fig))

        stds.columns = ["Column", "Std Dev"]
        fig2 = px.bar(
            stds, x="Column", y="Std Dev",
            title="Standard Deviation",
            color="Column", color_discrete_sequence=pal, text_auto=".2f")
        fig2.update_layout(**chart_layout())
        charts.append(("Standard Deviation", fig2))

    return charts
