"""
modules/analysis/pie_chart.py
Pie / Donut charts with Top-N and "Other" grouping support.
"""

import plotly.express as px
import pandas as pd
from modules.charts import chart_layout, COLORS, cat_cols as _cat_cols


def _sort_df(df_target, col_x, col_y, sort_by):
    if sort_by == "Value (Desc)":   return df_target.sort_values(col_y, ascending=False)
    if sort_by == "Value (Asc)":    return df_target.sort_values(col_y, ascending=True)
    if sort_by == "Category (A-Z)": return df_target.sort_values(col_x, ascending=True)
    if sort_by == "Category (Z-A)": return df_target.sort_values(col_x, ascending=False)
    return df_target


def _apply_top_n(df_agg, name_col, val_col, top_n, group_others=True):
    """Keep top N rows; bundle the rest into 'Other'."""
    if not top_n or top_n <= 0 or len(df_agg) <= top_n:
        return df_agg
    top    = df_agg.nlargest(top_n, val_col)
    rest   = df_agg[~df_agg[name_col].isin(top[name_col])]
    if group_others and len(rest) > 0:
        other_row = pd.DataFrame({name_col: ["Other"], val_col: [rest[val_col].sum()]})
        top = pd.concat([top, other_row], ignore_index=True)
    return top


def run_pie_chart(df, x_cols=None, y_cols=None, agg="mean", sort_by=None,
                  palette=None, top_n=None, **kwargs):
    """
    Args:
        x_cols:   list of categorical dimension columns
        y_cols:   list of numeric metric columns (optional)
        agg:      aggregation string
        sort_by:  sort preference
        palette:  list of hex colours
        top_n:    int — show only top N slices (rest → 'Other')

    Returns:
        list of (title, fig) tuples
    """
    charts    = []
    dims      = x_cols or _cat_cols()[:2]
    metrics   = y_cols
    agg_label = agg.title()
    pal       = palette or COLORS

    for col in dims:
        if metrics:
            for metric in metrics:
                agg_vals = df.groupby(col)[metric].agg(agg).reset_index()
                agg_vals.columns = [col, "Value"]
                agg_vals = _sort_df(agg_vals, col, "Value", sort_by)
                agg_vals = _apply_top_n(agg_vals, col, "Value", top_n)

                title_suffix = f" (Top {top_n})" if top_n and len(df[col].unique()) > top_n else ""
                fig = px.pie(
                    agg_vals, names=col, values="Value",
                    title=f"{agg_label} {metric} Split by {col}{title_suffix}",
                    color_discrete_sequence=pal, hole=0.45)
                fig.update_layout(**chart_layout())
                charts.append((f"Pie: {col}", fig))
        else:
            vc = df[col].value_counts().reset_index()
            vc.columns = [col, "Count"]
            vc = _sort_df(vc, col, "Count", sort_by)
            vc = _apply_top_n(vc, col, "Count", top_n)

            title_suffix = f" (Top {top_n})" if top_n and len(df[col].unique()) > top_n else ""
            fig = px.pie(
                vc, names=col, values="Count",
                title=f"Distribution of {col}{title_suffix}",
                color_discrete_sequence=pal, hole=0.45)
            fig.update_layout(**chart_layout())
            charts.append((f"Pie Counts: {col}", fig))

    return charts
