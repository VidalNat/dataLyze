"""
modules/analysis/distribution.py -- Distribution histogram runner.
=================================================================

Produces one histogram + box-plot marginal per selected numeric column.
The box-plot marginal sits above the histogram and lets users quickly spot
skew, quartiles, and outliers alongside the frequency distribution.

Each chart is coloured with a different palette entry so a dashboard
containing multiple distribution charts is visually distinguishable at a glance.
"""

import plotly.express as px
from modules.charts import chart_layout, COLORS, num_cols as _num_cols


def run_distribution(df, x_cols=None, y_cols=None, palette=None, **kwargs):
    """
    Generate histogram + box-plot marginal charts for numeric columns.

    Args:
        df:      Working DataFrame.
        x_cols:  Numeric columns to plot. Defaults to the first 6 numeric cols.
        y_cols:  Optional list containing one categorical column for colour-split.
                 When provided, each histogram bar is split by category.
        palette: List of hex colour strings.
        **kwargs: Extra kwargs silently ignored.

    Returns:
        list of (title: str, fig: Figure) -- one entry per column in x_cols.
    """
    charts = []
    num = x_cols or _num_cols()[:6]  # Cap default at 6 to avoid overwhelming output.
    pal = palette or COLORS

    # ── Sample for performance: Plotly still sends raw bin data ────────────────
    from modules.utils.perf import sample_for_plot
    plot_df, sampled = sample_for_plot(df, n=100_000)
    sample_note = f"  (100 K sample of {len(df):,} rows)" if sampled else ""

    for i, col in enumerate(num):
        fig = px.histogram(
            plot_df,
            x=col,
            nbins=35,
            marginal="box",
            title=f"Distribution: {col}" + sample_note,
            color_discrete_sequence=[pal[i % len(pal)]])
        fig.update_layout(**chart_layout())
        if sampled:
            fig.add_annotation(
                text=f"⚠️ Showing 100,000-row sample of {len(df):,} total rows",
                xref="paper", yref="paper", x=0, y=-0.12,
                showarrow=False, font=dict(size=10, color="#f59e0b")
            )
        charts.append((f"Dist: {col}", fig))

    return charts
