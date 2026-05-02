"""
modules/analysis/outlier.py -- IQR-based outlier detection runner.
=================================================================

Identifies and visualises statistical outliers using the interquartile range
(IQR) method -- the most common non-parametric outlier detection technique.

Method:
    Q1  = 25th percentile
    Q3  = 75th percentile
    IQR = Q3 - Q1
    Lower fence = Q1 - 1.5 × IQR
    Upper fence = Q3 + 1.5 × IQR

    Any value outside [Lower fence, Upper fence] is flagged as an outlier.

Chart design:
    - Normal points:  small semi-transparent dots (low visual weight).
    - Outlier points: large red × markers (immediately visible).
    - Dashed horizontal lines mark the IQR fences.
    - X-axis shows the DataFrame row index so users can locate the exact
      row in their data after identifying an outlier of interest.
    - Hover tooltip shows "Row index / column value" clearly.

OUTLIER_HELP is a markdown string rendered by the analysis page above the
charts to explain how to interpret the visualisation -- written for business
users rather than statisticians.
"""

import streamlit as st
import plotly.graph_objects as go
from modules.charts import chart_layout, COLORS


def run_outlier(df, x_cols=None, y_cols=None, palette=None, **kwargs):
    """
    Generate IQR-based outlier scatter plots for each selected numeric column.

    Args:
        df:      Working DataFrame.
        x_cols:  Numeric columns to analyse. Defaults to the first 6 numeric cols.
        y_cols:  Optional list with one categorical column for grouping (future use).
        palette: List of hex colour strings. Index 0 is used for normal points.
        **kwargs: Extra kwargs silently ignored.

    Returns:
        list of (title: str, fig: Figure) -- one entry per column in x_cols.
    """
    charts = []
    from modules.charts import num_cols as _num_cols
    num = x_cols or _num_cols()[:6]
    pal = palette or COLORS

    for col in num:
        # ── Compute IQR fences ────────────────────────────────────────────────
        Q1, Q3 = df[col].quantile(0.25), df[col].quantile(0.75)
        IQR    = Q3 - Q1
        lo     = Q1 - 1.5 * IQR
        hi     = Q3 + 1.5 * IQR

        out_mask = (df[col] < lo) | (df[col] > hi)
        out      = df[out_mask].copy()   # Outlier rows
        nrm      = df[~out_mask].copy()  # Normal rows

        fig = go.Figure()

        # ── Normal points -- low-weight dots ───────────────────────────────────
        fig.add_trace(go.Scatter(
            x=nrm.index,
            y=nrm[col].values,
            mode="markers",
            name="Normal",
            marker=dict(color=pal[0], size=4, opacity=0.45),
            hovertemplate=(
                f"<b>Row:</b> %{{x}}<br>"
                f"<b>{col}:</b> %{{y:,.2f}}<br>"
                "<extra>Normal</extra>"
            )
        ))

        # ── Outlier points -- prominent red × markers ──────────────────────────
        fig.add_trace(go.Scatter(
            x=out.index,
            y=out[col].values,
            mode="markers",
            name="Outlier ⚠️",
            marker=dict(color="#ef4444", size=9, symbol="x"),
            hovertemplate=(
                f"<b>Row:</b> %{{x}}<br>"
                f"<b>{col}:</b> %{{y:,.2f}}<br>"
                "<extra>⚠️ Outlier</extra>"
            )
        ))

        # ── IQR fence lines ───────────────────────────────────────────────────
        fig.add_hline(
            y=hi, line_dash="dash", line_color="#f59e0b",
            annotation_text=f"Upper IQR boundary: {hi:.2f}",
            annotation_position="top right")
        fig.add_hline(
            y=lo, line_dash="dash", line_color="#f59e0b",
            annotation_text=f"Lower IQR boundary: {lo:.2f}",
            annotation_position="bottom right")

        n_out = len(out)
        fig.update_layout(
            title=f"Outliers -- {col}  ({n_out} outlier{'s' if n_out != 1 else ''} detected)",
            xaxis_title="Row Index (hover to see exact row number)",
            yaxis_title=col,
            **chart_layout()
        )
        charts.append((f"Outliers: {col}", fig))

    return charts


# ─────────────────────────────────────────────────────────────────────────────
# Help text -- rendered by pages/analysis.py above the generated charts
# ─────────────────────────────────────────────────────────────────────────────

OUTLIER_HELP = (
    "**📊 How to read Outlier charts:**  "
    "Each dot is one row in your dataset. "
    "**🔴 Red × marks** are outliers -- values that fall outside the IQR boundaries (dashed lines). "
    "**Hover** over any point to see its exact Row Index and value. "
    "The row index maps directly to the row number in your raw data table.\n\n"
    "**Business use:** Outliers often signal data-entry errors, fraud, returns, or exceptional events. "
    "Investigate red points before running predictive models -- they can skew results significantly."
)
