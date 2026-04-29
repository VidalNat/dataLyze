"""
modules/analysis/categorical.py
Vertical column charts AND horizontal bar charts.
Top-N, dual Y-axis (bar + line), text values outside bars.
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
from modules.charts import chart_layout, COLORS, cat_cols as _cat_cols

_SORT = {
    "Value (Desc)":   lambda d, vc: d.sort_values(vc, ascending=False),
    "Value (Asc)":    lambda d, vc: d.sort_values(vc, ascending=True),
    "Category (A-Z)": lambda d, vc: d.sort_values(d.columns[0], ascending=True),
    "Category (Z-A)": lambda d, vc: d.sort_values(d.columns[0], ascending=False),
}


def _sort(df, val_col, sort_by):
    fn = _SORT.get(sort_by)
    return fn(df, val_col) if fn else df


def _apply_plotly_sort(fig, cats, is_horiz, sort_by):
    """
    Force Plotly to respect the DataFrame's sorted order.
    For horizontal bars, Plotly renders list bottom→top, so we also
    reverse the category array so the 'first' sorted item appears at top.
    """
    if is_horiz:
        # categoryarray sets explicit order top→bottom when reversed
        fig.update_yaxes(categoryorder="array", categoryarray=list(reversed(cats)))
    else:
        fig.update_xaxes(categoryorder="array", categoryarray=cats)
    return fig


def run_categorical(df, x_cols=None, y_cols=None, agg="mean", sort_by=None,
                    palette=None, top_n=None, dual_y_col=None,
                    direction="Vertical (Column chart)", **_):
    charts   = []
    dims     = x_cols or _cat_cols()[:4]
    metrics  = y_cols
    agg_lbl  = agg.title()
    pal      = palette or COLORS
    is_horiz = "Horizontal" in str(direction)

    for col in dims:
        if metrics:
            for metric in metrics:
                agg_df = df.groupby(col)[metric].agg(agg).reset_index()
                agg_df.columns = [col, "val"]
                agg_df = _sort(agg_df, "val", sort_by)
                if top_n and top_n > 0:
                    agg_df = agg_df.nlargest(top_n, "val")
                agg_df = agg_df.reset_index(drop=True)
                top_sfx = f" (Top {top_n})" if top_n else ""

                # ── Dual Y ────────────────────────────────────────────────────
                dual = dual_y_col
                if dual and dual in df.columns and dual != metric:
                    d2 = df.groupby(col)[dual].agg(agg).reset_index()
                    d2.columns = [col, "val2"]
                    merged = agg_df.merge(d2, on=col, how="left")
                    cats   = merged[col].tolist()
                    v1     = merged["val"].tolist()
                    v2     = merged["val2"].tolist()

                    fig = make_subplots(specs=[[{"secondary_y": True}]])
                    bar_x, bar_y = (v1, cats) if is_horiz else (cats, v1)
                    fig.add_trace(go.Bar(
                        x=bar_x, y=bar_y,
                        orientation="h" if is_horiz else "v",
                        name=f"{agg_lbl} {metric}",
                        marker_color=pal[0],
                        text=[f"{v:,.1f}" for v in v1],
                        textposition="outside",
                        cliponaxis=False,
                    ), secondary_y=False)
                    fig.add_trace(go.Scatter(
                        x=cats, y=v2,
                        name=f"{agg_lbl} {dual}",
                        mode="lines+markers",
                        line=dict(color=pal[1], width=2),
                        marker=dict(size=8),
                    ), secondary_y=True)
                    fig.update_layout(
                        title=f"{agg_lbl} {metric} & {dual} by {col}{top_sfx}",
                        **chart_layout())
                    fig.update_yaxes(title_text=f"{agg_lbl} {metric}", secondary_y=False)
                    fig.update_yaxes(title_text=f"{agg_lbl} {dual}",   secondary_y=True)
                    if is_horiz:
                        fig.update_layout(margin=dict(l=20, r=100, t=56, b=20))
                    _apply_plotly_sort(fig, cats, is_horiz, sort_by)
                else:
                    cats  = agg_df[col].tolist()
                    vals  = agg_df["val"].tolist()
                    texts = [f"{v:,.1f}" for v in vals]
                    bar_x, bar_y = (vals, cats) if is_horiz else (cats, vals)
                    colors = [pal[i % len(pal)] for i in range(len(cats))]
                    fig = go.Figure(go.Bar(
                        x=bar_x, y=bar_y,
                        orientation="h" if is_horiz else "v",
                        marker_color=colors,
                        text=texts,
                        textposition="outside",
                        cliponaxis=False,
                    ))
                    d_lbl = "Bar" if is_horiz else "Column"
                    fig.update_layout(
                        title=f"{d_lbl}: {agg_lbl} {metric} by {col}{top_sfx}",
                        showlegend=False,
                        **chart_layout())
                    if is_horiz:
                        fig.update_layout(margin=dict(l=20, r=100, t=56, b=20))
                    else:
                        fig.update_layout(margin=dict(l=20, r=20, t=56, b=60))
                    _apply_plotly_sort(fig, cats, is_horiz, sort_by)

                charts.append((f"{agg_lbl} {metric} by {col}", fig))

        else:
            vc = df[col].value_counts().reset_index()
            vc.columns = [col, "Count"]
            vc = _sort(vc, "Count", sort_by)
            if top_n and top_n > 0:
                vc = vc.nlargest(top_n, "Count")
            vc = vc.reset_index(drop=True)
            top_sfx = f" (Top {top_n})" if top_n else ""

            cats   = vc[col].tolist()
            vals   = vc["Count"].tolist()
            texts  = [str(v) for v in vals]
            bar_x, bar_y = (vals, cats) if is_horiz else (cats, vals)
            colors = [pal[i % len(pal)] for i in range(len(cats))]
            d_lbl  = "Bar" if is_horiz else "Column"

            fig = go.Figure(go.Bar(
                x=bar_x, y=bar_y,
                orientation="h" if is_horiz else "v",
                marker_color=colors,
                text=texts,
                textposition="outside",
                cliponaxis=False,
            ))
            fig.update_layout(
                title=f"{d_lbl} Counts: {col}{top_sfx}",
                showlegend=False,
                **chart_layout())
            if is_horiz:
                fig.update_layout(margin=dict(l=20, r=100, t=56, b=20))
            _apply_plotly_sort(fig, cats, is_horiz, sort_by)

            charts.append((f"Counts: {col}", fig))

    return charts
