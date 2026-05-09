"""
modules/analysis/matrix_table.py -- Pivot table & heatmap runner.
=================================================================

Cross-tabulates two categorical columns over a numeric value and renders as
an interactive heatmap (go.Heatmap) or styled pivot table (go.Table).

Fixes over previous version:
  - Uses go.Heatmap directly — px.imshow produced tiny unscaled figures
  - Explicit height scales with number of rows (min 420, max 800)
  - All axis labels, tick text, colorbar title rendered in light colours
  - RdBu diverging scale for mean/median/std; sequential Blues for others
  - Pivot capped at 40 × 40 categories for readability
  - Hover shows index label, column label, and formatted aggregate value
  - Robust applymap → map compatibility (pandas 2.1+)
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from modules.charts import chart_layout, COLORS, num_cols as _num_cols, cat_cols as _cat_cols

_DIVERGING_AGGS = {"mean", "median", "std"}
_MAX_CATS       = 40


def _trim_pivot(pivot: pd.DataFrame, max_cats: int) -> pd.DataFrame:
    if pivot.shape[0] > max_cats:
        pivot = pivot.loc[pivot.abs().sum(axis=1).nlargest(max_cats).index]
    if pivot.shape[1] > max_cats:
        pivot = pivot[pivot.abs().sum(axis=0).nlargest(max_cats).index]
    return pivot


def _sort_pivot(pivot: pd.DataFrame) -> pd.DataFrame:
    try:
        row_order = pivot.mean(axis=1).sort_values(ascending=False).index
        col_order = pivot.mean(axis=0).sort_values(ascending=False).index
        return pivot.loc[row_order, col_order]
    except Exception:
        return pivot


def _fmt(v) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return ""
    try:
        if abs(v) >= 1_000_000:
            return f"{v / 1_000_000:,.1f} M"
        if abs(v) >= 1_000:
            return f"{v:,.0f}"
        return f"{v:,.2f}"
    except Exception:
        return str(v)


def run_matrix_table(df, index_col=None, columns_col=None, values_col=None,
                     agg="mean", view_type="Heatmap", palette=None, **kwargs):
    charts = []
    cats   = _cat_cols()
    num    = _num_cols()
    pal    = palette or COLORS

    idx  = index_col  or (cats[0] if cats else df.columns[0])
    cols = columns_col or (cats[1] if len(cats) > 1 else df.columns[1])
    num_fallback = list(df.select_dtypes("number").columns)
    vals = values_col or (num[0] if num else (num_fallback[0] if num_fallback else None))

    if not vals or idx not in df.columns or cols not in df.columns or vals not in df.columns:
        return []

    # ── Build pivot ───────────────────────────────────────────────────────────
    try:
        pivot = pd.pivot_table(
            df, index=idx, columns=cols, values=vals,
            aggfunc=agg, observed=True,
        )
        # Flatten MultiIndex columns if present
        if isinstance(pivot.columns, pd.MultiIndex):
            pivot.columns = [" · ".join(str(c) for c in col).strip() for col in pivot.columns]
        if isinstance(pivot.index, pd.MultiIndex):
            pivot.index = [" · ".join(str(c) for c in row).strip() for row in pivot.index]
    except Exception as exc:
        return []

    pivot = _trim_pivot(pivot, _MAX_CATS)
    pivot = _sort_pivot(pivot)

    n_rows, n_cols_p = pivot.shape
    if n_rows == 0 or n_cols_p == 0:
        return []

    agg_label  = agg.upper()
    trunc_note = ""
    tr = df[idx].nunique()
    tc = df[cols].nunique()
    if tr > _MAX_CATS or tc > _MAX_CATS:
        trunc_note = f"  (top {n_rows}×{n_cols_p} of {tr}×{tc})"
    base_title = f"Matrix ({agg_label}): {vals}  ·  {idx} × {cols}{trunc_note}"

    # Dynamic height: scale with row count, clamp [420, 800]
    height = max(420, min(n_rows * 30 + 160, 800))

    z_values = pivot.values.tolist()
    x_labels = [str(c) for c in pivot.columns]
    y_labels  = [str(r) for r in pivot.index]

    use_diverging = agg in _DIVERGING_AGGS
    colorscale    = "RdBu" if use_diverging else "Blues"

    flat = [v for row in z_values for v in row
            if v is not None and not (isinstance(v, float) and np.isnan(v))]
    zmid = float(np.mean(flat)) if use_diverging and flat else None
    zmin = float(min(flat))     if (not use_diverging and flat) else None
    zmax = float(max(flat))     if (not use_diverging and flat) else None

    text_vals = [[_fmt(v) for v in row] for row in z_values]

    # ── Heatmap ───────────────────────────────────────────────────────────────
    if view_type == "Heatmap":
        # Text colour: white when background is dark (low z), dark when light
        fig = go.Figure(go.Heatmap(
            z=z_values,
            x=x_labels,
            y=y_labels,
            text=text_vals,
            texttemplate="%{text}",
            textfont=dict(size=10, color="white"),
            colorscale=colorscale,
            zmid=zmid,
            zmin=zmin,
            zmax=zmax,
            hoverongaps=False,
            hovertemplate=(
                f"<b>{idx}:</b> %{{y}}<br>"
                f"<b>{cols}:</b> %{{x}}<br>"
                f"<b>{agg_label}({vals}):</b> %{{z:,.3f}}"
                "<extra></extra>"
            ),
            colorbar=dict(
                title=dict(
                    text=f"{agg_label}({vals})",
                    side="right",
                    font=dict(color="#cbd5e1", size=11),
                ),
                tickfont=dict(color="#94a3b8", size=10),
                thickness=14, len=0.85,
                bgcolor="rgba(15,23,42,0.4)",
                bordercolor="rgba(100,116,139,0.3)",
                borderwidth=1,
            ),
        ))

        axis_common = dict(
            tickfont=dict(color="#94a3b8", size=10),
            gridcolor="rgba(100,116,139,0.15)",
            linecolor="rgba(100,116,139,0.25)",
            automargin=True,
        )
        _layout = chart_layout(height=height)
        _layout["margin"] = dict(l=10, r=100, t=58, b=90)
        fig.update_layout(
            **_layout,
            title=dict(text=base_title, font=dict(color="#e2e8f0", size=13)),
            xaxis=dict(
                **axis_common,
                title=dict(text=cols, font=dict(color="#cbd5e1", size=12)),
                tickangle=-30,
                side="bottom",
            ),
            yaxis=dict(
                **axis_common,
                title=dict(text=idx, font=dict(color="#cbd5e1", size=12)),
                autorange="reversed",
            ),
        )
        charts.append((f"Matrix Heatmap: {idx} × {cols}", fig))

    # ── Table ─────────────────────────────────────────────────────────────────
    else:
        col_headers = [idx] + x_labels
        index_vals  = y_labels
        data_cols   = [[_fmt(row[j]) for row in z_values] for j in range(n_cols_p)]

        n_data_rows = len(index_vals)
        row_fills   = ["#1e293b" if i % 2 == 0 else "#172033" for i in range(n_data_rows)]
        hdr_color   = pal[0] if pal else "#4f6ef7"

        fig = go.Figure(go.Table(
            columnwidth=[2] + [1] * n_cols_p,
            header=dict(
                values=[f"<b>{h}</b>" for h in col_headers],
                fill_color=hdr_color,
                font=dict(color="white", size=12),
                align=["left"] + ["right"] * n_cols_p,
                height=32,
            ),
            cells=dict(
                values=[index_vals] + data_cols,
                fill_color=[row_fills] * len(col_headers),
                font=dict(color="#f1f5f9", size=11),
                align=["left"] + ["right"] * n_cols_p,
                height=26,
            ),
        ))

        # Column average footer row
        col_avgs   = [np.nanmean([row[j] for row in z_values
                                  if row[j] is not None and not np.isnan(row[j])])
                      for j in range(n_cols_p)]
        totals_fmt = [_fmt(v) if not np.isnan(v) else "—" for v in col_avgs]
        fig.add_trace(go.Table(
            columnwidth=[2] + [1] * n_cols_p,
            header=dict(values=[""] * len(col_headers),
                        fill_color="rgba(0,0,0,0)", line_color="rgba(0,0,0,0)", height=0),
            cells=dict(
                values=[["<b>Col avg</b>"]] + [[f"<b>{v}</b>"] for v in totals_fmt],
                fill_color=["#0f172a"],
                font=dict(color="#818cf8", size=11),
                align=["left"] + ["right"] * n_cols_p,
                height=28,
            ),
        ))

        _layout = chart_layout(height=max(height, 480))
        _layout["margin"] = dict(l=10, r=10, t=58, b=10)
        fig.update_layout(
            **_layout,
            title=dict(text=base_title, font=dict(color="#e2e8f0", size=13)),
        )
        charts.append((f"Matrix Table: {idx} × {cols}", fig))

    return charts
