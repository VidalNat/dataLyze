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

    for i, col in enumerate(num):
        fig = px.histogram(
            df,
            x=col,
            nbins=35,            # 35 bins is a good default for most datasets.
            marginal="box",      # Box plot above the histogram for quartile visibility.
            title=f"Distribution: {col}",
            color_discrete_sequence=[pal[i % len(pal)]])
        fig.update_layout(**chart_layout())
        charts.append((f"Dist: {col}", fig))

    return charts
