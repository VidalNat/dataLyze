"""
modules/analysis/matrix_table.py -- Pivot table & heatmap runner.
=================================================================

Cross-tabulates two categorical columns over a numeric value and renders
as an interactive heatmap or styled pivot table.

Refinements over v1:
  - Diverging colour scale (RdBu) for mean/zscore-like aggs; sequential
    (Blues) for sum/count/min/max — chosen automatically
  - Pivot rows and columns are sorted by their marginal mean for readability
  - Row and column totals appended as marginal annotations on the heatmap
  - Table view: alternating row shading, bold totals row, right-aligned numbers
  - Pivot is capped at 40×40 categories to keep the chart usable
  - fill_value uses NaN → shown as blank in heatmap (not misleading 0)
"""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from modules.charts import chart_layout, COLORS, num_cols as _num_cols, cat_cols as _cat_cols

# Aggregations whose natural zero is meaningful → use diverging scale
_DIVERGING_AGGS = {"mean", "median", "std"}

_MAX_CATS = 40   # cap rows/cols to keep chart readable


def _trim_pivot(pivot: pd.DataFrame, max_cats: int) -> pd.DataFrame:
    """Keep the top max_cats rows/cols by their row/col sum magnitude."""
    if pivot.shape[0] > max_cats:
        row_sums = pivot.abs().sum(axis=1).nlargest(max_cats).index
        pivot    = pivot.loc[row_sums]
    if pivot.shape[1] > max_cats:
        col_sums = pivot.abs().sum(axis=0).nlargest(max_cats).index
        pivot    = pivot[col_sums]
    return pivot


def _sort_pivot(pivot: pd.DataFrame) -> pd.DataFrame:
    """Sort rows and columns by their marginal mean (largest first)."""
    try:
        row_order = pivot.mean(axis=1).sort_values(ascending=False).index
        col_order = pivot.mean(axis=0).sort_values(ascending=False).index
        return pivot.loc[row_order, col_order]
    except Exception:
        return pivot


def run_matrix_table(df, index_col=None, columns_col=None, values_col=None,
                     agg="mean", view_type="Heatmap", palette=None, **kwargs):
    charts = []
    cats   = _cat_cols()
    num    = _num_cols()
    pal    = palette or COLORS

    idx  = index_col  or (cats[0] if cats else df.columns[0])
    cols = columns_col or (cats[1] if len(cats) > 1 else df.columns[1])
    vals = values_col  or (num[0]  if num  else df.select_dtypes("number").columns[0])

    if idx not in df.columns or cols not in df.columns or vals not in df.columns:
        return []

    # ── Build pivot ───────────────────────────────────────────────────────────
    pivot = df.pivot_table(
        index=idx, columns=cols, values=vals,
        aggfunc=agg,
        # NaN for missing combos — shown as blank in heatmap (not misleading 0)
    )
    pivot = _trim_pivot(pivot, _MAX_CATS)
    pivot = _sort_pivot(pivot)

    # Truncation note for the title
    n_rows, n_cols = pivot.shape
    trunc_note = ""
    total_rows = df[idx].nunique()
    total_cols = df[cols].nunique()
    if total_rows > _MAX_CATS or total_cols > _MAX_CATS:
        trunc_note = f"  (top {n_rows}×{n_cols} of {total_rows}×{total_cols})"

    base_title = f"Matrix ({agg.upper()}): {vals} by {idx} × {cols}{trunc_note}"

    # ── Colour scale ──────────────────────────────────────────────────────────
    use_diverging = agg in _DIVERGING_AGGS
    cscale        = "RdBu"  if use_diverging else "Blues"
    cmid          = float(pivot.stack().mean()) if use_diverging else None

    # ── Heatmap view ──────────────────────────────────────────────────────────
    if view_type == "Heatmap":
        # Annotate with formatted values; blank for NaN cells
        text_matrix = pivot.applymap(
            lambda v: f"{v:,.2f}" if pd.notna(v) else ""
        ).values

        fig = px.imshow(
            pivot,
            text_auto=False,
            aspect="auto",
            title=base_title,
            color_continuous_scale=cscale,
            color_continuous_midpoint=cmid,
            zmin=pivot.min().min() if not use_diverging else None,
        )

        # Custom text layer so we control formatting
        fig.update_traces(
            text=text_matrix,
            texttemplate="%{text}",
            textfont=dict(size=10),
        )

        # ── Marginal row/col totals as annotations along the edges ────────────
        try:
            row_means = pivot.mean(axis=1)
            col_means = pivot.mean(axis=0)

            # Right-side row mean labels
            for i, (ridx, rmean) in enumerate(row_means.items()):
                if pd.notna(rmean):
                    fig.add_annotation(
                        x=n_cols - 0.5 + 0.85, y=i,
                        text=f"{rmean:,.1f}",
                        xref="x", yref="y",
                        showarrow=False,
                        font=dict(size=9, color="#64748b"),
                        xanchor="left",
                    )

            # Bottom column mean labels
            for j, (cidx, cmean) in enumerate(col_means.items()):
                if pd.notna(cmean):
                    fig.add_annotation(
                        x=j, y=n_rows - 0.5 + 0.85,
                        text=f"{cmean:,.1f}",
                        xref="x", yref="y",
                        showarrow=False,
                        font=dict(size=9, color="#64748b"),
                        yanchor="top",
                    )
        except Exception:
            pass

        fig.update_layout(
            **chart_layout(),
            xaxis=dict(side="bottom", tickangle=-30, title=cols),
            yaxis=dict(title=idx),
            coloraxis_colorbar=dict(
                title=dict(text=f"{agg}({vals})", side="right"),
                thickness=14, len=0.85,
            ),
            margin=dict(r=80, b=80),   # room for marginal annotations
        )

        charts.append((f"Matrix Heatmap: {idx} × {cols}", fig))

    # ── Table view ────────────────────────────────────────────────────────────
    else:
        # Compute totals row for context
        totals_row = pivot.mean(axis=0)

        col_headers = [idx] + [str(c) for c in pivot.columns]

        # Build cell values: index column + one column per pivot column
        index_vals = list(pivot.index)
        data_cols  = [
            [f"{v:,.2f}" if pd.notna(v) else "—" for v in pivot[c]]
            for c in pivot.columns
        ]

        # Alternating row fill for readability
        n_data_rows = len(index_vals)
        row_fills   = [
            "#1e293b" if i % 2 == 0 else "#172033"
            for i in range(n_data_rows)
        ]

        # Header colour from palette
        hdr_color = pal[0] if pal else "#4f6ef7"

        fig = go.Figure(data=[go.Table(
            columnwidth=[2] + [1] * len(pivot.columns),
            header=dict(
                values=[f"<b>{h}</b>" for h in col_headers],
                fill_color=hdr_color,
                font=dict(color="white", size=12),
                align=["left"] + ["right"] * len(pivot.columns),
                height=32,
            ),
            cells=dict(
                values=[index_vals] + data_cols,
                fill_color=[row_fills] * len(col_headers),
                font=dict(color="#f1f5f9", size=11),
                align=["left"] + ["right"] * len(pivot.columns),
                height=26,
            ),
        )])

        # Append totals row as a second table trace (visually separated)
        totals_vals = [f"<b>{v:,.2f}</b>" if pd.notna(v) else "—" for v in totals_row]
        fig.add_trace(go.Table(
            columnwidth=[2] + [1] * len(pivot.columns),
            header=dict(
                values=[""] * len(col_headers),
                fill_color="rgba(0,0,0,0)",
                line_color="rgba(0,0,0,0)",
                height=0,
            ),
            cells=dict(
                values=[["<b>Col avg</b>"]] + [[v] for v in totals_vals],
                fill_color=["#0f172a"],
                font=dict(color="#818cf8", size=11),
                align=["left"] + ["right"] * len(pivot.columns),
                height=28,
            ),
        ))

        fig.update_layout(
            title=base_title,
            **chart_layout(),
        )
        charts.append((f"Matrix Table: {idx} × {cols}", fig))

    return charts
