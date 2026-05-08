"""
modules/analysis/scatter_plot.py -- Scatter plot runner.
=========================================================

Visualises the relationship between two numeric variables with optional
colour grouping, size encoding, and trendlines.

Refinements over v1:
  - Adaptive marker opacity by point density (fewer points → more opaque)
  - Pearson r annotation on the chart when no colour grouping is active
  - Marginal rug plots on X and Y axes for distribution context (≤5 K pts)
  - Normalised size encoding: maps size column to a sensible pixel range
  - WebGL render mode for snappy interaction on large samples
  - Sample warning rendered inside the plot area, not below it
"""
import numpy as np
import plotly.express as px
from modules.charts import chart_layout, COLORS, num_cols as _num_cols
from modules.utils.perf import sample_for_plot


def _pearson_r(a, b):
    """Return Pearson r between two series, or None on failure."""
    try:
        import pandas as pd
        s1 = pd.to_numeric(a, errors="coerce").dropna()
        s2 = pd.to_numeric(b, errors="coerce").dropna()
        idx = s1.index.intersection(s2.index)
        if len(idx) < 3:
            return None
        return float(np.corrcoef(s1[idx], s2[idx])[0, 1])
    except Exception:
        return None


def _opacity(n: int) -> float:
    if n < 500:    return 0.85
    if n < 2_000:  return 0.65
    if n < 10_000: return 0.45
    return 0.30


def run_scatter_plot(df, x_col=None, y_col=None, color_col=None, size_col=None,
                     trendline=None, palette=None, **kwargs):
    charts = []
    num = _num_cols()
    pal = palette or COLORS

    x = x_col or (num[0] if num else None)
    y = y_col or (num[1] if len(num) > 1 else num[0] if num else None)
    if not x or not y or x not in df.columns or y not in df.columns:
        return []

    color = color_col if color_col and color_col in df.columns else None
    tl    = trendline  if trendline  and trendline  != "None" else None

    # Size column: only use it when it has variance
    size = None
    if size_col and size_col in df.columns:
        try:
            if df[size_col].dropna().nunique() > 1:
                size = size_col
        except Exception:
            pass

    # ── Performance sample ────────────────────────────────────────────────────
    plot_df, sampled = sample_for_plot(df, n=50_000)
    n_pts   = len(plot_df)
    opacity = _opacity(n_pts)

    # ── Pearson r (skip when colour-grouped — r would be misleading) ──────────
    r_val = _pearson_r(plot_df[x], plot_df[y]) if not color else None

    # ── Title ─────────────────────────────────────────────────────────────────
    r_str      = f"  |  r = {r_val:+.3f}" if r_val is not None else ""
    sample_str = f"  (50 K sample of {len(df):,})" if sampled else ""
    title      = f"Scatter: {x} vs {y}{r_str}{sample_str}"

    # Marginal rugs only for smaller plots — rug traces are expensive at scale
    marginal = "rug" if n_pts <= 5_000 else None

    fig = px.scatter(
        plot_df, x=x, y=y,
        color=color,
        size=size,
        size_max=36,
        trendline=tl,
        marginal_x=marginal,
        marginal_y=marginal,
        title=title,
        color_discrete_sequence=pal,
        opacity=opacity,
        render_mode="webgl",
    )

    # Crisp marker borders help distinguish overlapping points
    fig.update_traces(
        selector=dict(mode="markers"),
        marker=dict(line=dict(width=0.5, color="rgba(255,255,255,0.25)")),
    )
    if tl:
        fig.update_traces(
            selector=dict(mode="lines"),
            line=dict(width=2, dash="dot"),
        )

    fig.update_layout(
        **chart_layout(),
        xaxis_title=x,
        yaxis_title=y,
        legend=dict(orientation="v", x=1.01, y=1),
    )

    # ── Inline r annotation ───────────────────────────────────────────────────
    if r_val is not None:
        strength  = "strong" if abs(r_val) >= 0.7 else "moderate" if abs(r_val) >= 0.4 else "weak"
        direction = "positive" if r_val > 0 else "negative"
        fig.add_annotation(
            text=f"r = {r_val:+.3f}  ({strength} {direction})",
            xref="paper", yref="paper", x=0.01, y=0.99,
            showarrow=False, xanchor="left", yanchor="top",
            font=dict(size=11, color="#94a3b8"),
            bgcolor="rgba(15,23,42,0.55)", borderpad=4,
        )

    if sampled:
        fig.add_annotation(
            text=f"⚠ 50 K-row sample of {len(df):,} total rows",
            xref="paper", yref="paper", x=0.5, y=-0.13,
            showarrow=False, xanchor="center",
            font=dict(size=10, color="#f59e0b"),
        )

    charts.append((f"Scatter: {x} vs {y}", fig))
    return charts
