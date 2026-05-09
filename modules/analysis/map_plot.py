"""
modules/analysis/map_plot.py -- Geographic scatter/bubble runner.
=================================================================

Plots data points on an interactive OpenStreetMap using lat/lon columns.
Supports:
  - Size encoding (marker size ∝ numeric column, normalised)
  - Colour grouping (categorical or numeric)
  - Value aggregation: when a location label column AND a value column are both
    set, rows are grouped by location first (sum/mean/etc.) so you see ONE
    marker per location with the aggregated value in the hover tooltip.
  - Rich hover: location name, aggregated value, lat/lon
  - Auto-zoom to bounding box of the data
  - Hard cap of 5 K raw points (before agg) to prevent browser freeze

Uses px.scatter_mapbox (stable, no token needed with open-street-map style).
"""
import numpy as np
import pandas as pd
import plotly.express as px
from modules.charts import chart_layout, COLORS
from modules.utils.perf import sample_for_plot

_MAP_SAMPLE = 5_000   # raw-point cap before aggregation


def _auto_zoom(lats, lons) -> tuple:
    try:
        spread = max(float(np.max(lats) - np.min(lats)),
                     float(np.max(lons) - np.min(lons)))
        for threshold, zoom in [
            (120, 1), (60, 2), (30, 3), (15, 4), (7, 5), (3, 6),
            (1.5, 7), (0.7, 8), (0.3, 9), (0.1, 10),
        ]:
            if spread > threshold:
                return float(np.mean(lats)), float(np.mean(lons)), zoom
        return float(np.mean(lats)), float(np.mean(lons)), 11
    except Exception:
        return 20.0, 0.0, 2


def _normalise_size(series: pd.Series, lo: float = 4, hi: float = 22) -> pd.Series:
    mn, mx = series.min(), series.max()
    if mx == mn:
        return pd.Series([float(lo + (hi - lo) / 2)] * len(series), index=series.index)
    return lo + (series - mn) / (mx - mn) * (hi - lo)


def run_map_plot(df, lat_col=None, lon_col=None, size_col=None, color_col=None,
                 value_col=None, agg_func=None, location_col=None,
                 palette=None, **kwargs):
    charts = []
    pal    = palette or COLORS

    # ── Auto-detect lat / lon ─────────────────────────────────────────────────
    num = [c for c in df.select_dtypes("number").columns]
    lat = lat_col or next((c for c in df.columns if "lat" in c.lower()), None)
    lon = lon_col or next(
        (c for c in df.columns
         if "lon" in c.lower() or "lng" in c.lower() or "long" in c.lower()), None)
    lat = lat or (num[0] if num else None)
    lon = lon or (num[1] if len(num) > 1 else None)

    if not lat or not lon or lat not in df.columns or lon not in df.columns:
        return []

    # ── Gather needed columns & clean ─────────────────────────────────────────
    needed = list({lat, lon})
    for c in (size_col, color_col, location_col, value_col):
        if c and c in df.columns:
            needed.append(c)
    clean_df = df[list(set(needed))].dropna(subset=[lat, lon]).copy()
    clean_df = clean_df[~((clean_df[lat] == 0) & (clean_df[lon] == 0))]
    if clean_df.empty:
        return []

    # ── Optional: aggregate by location before plotting ───────────────────────
    agg_label = ""
    sampled   = False
    loc_col   = location_col if location_col and location_col in clean_df.columns else None
    val_col   = value_col    if value_col    and value_col    in clean_df.columns else None

    if loc_col and val_col:
        agg = agg_func or "mean"
        agg_dict: dict = {lat: "first", lon: "first", val_col: agg}
        if color_col and color_col in clean_df.columns:
            agg_dict[color_col] = "first"
        if size_col and size_col in clean_df.columns and size_col != val_col:
            agg_dict[size_col] = agg
        plot_df   = clean_df.groupby(loc_col, as_index=False).agg(agg_dict)
        agg_label = f" · {agg.upper()}({val_col})"
    else:
        plot_df, sampled = sample_for_plot(clean_df, n=_MAP_SAMPLE)

    if plot_df.empty:
        return []

    # ── Validate encoding columns ─────────────────────────────────────────────
    size  = size_col  if size_col  and size_col  in plot_df.columns else None
    color = color_col if color_col and color_col in plot_df.columns else None
    hover = loc_col   if loc_col   and loc_col   in plot_df.columns else None

    # Normalise size to pixel range so no single marker dominates
    if size:
        try:
            raw = pd.to_numeric(plot_df[size], errors="coerce")
            if raw.dropna().nunique() > 1:
                plot_df = plot_df.copy()
                plot_df[size] = _normalise_size(raw.fillna(raw.median()))
            else:
                size = None
        except Exception:
            size = None

    # ── Auto-zoom ─────────────────────────────────────────────────────────────
    centre_lat, centre_lon, zoom = _auto_zoom(plot_df[lat], plot_df[lon])

    # ── Hover data ────────────────────────────────────────────────────────────
    hover_data: dict = {}
    for col in [val_col, size_col, color_col]:
        if col and col in plot_df.columns and col != hover:
            hover_data[col] = True
    hover_data[lat] = ":.4f"
    hover_data[lon] = ":.4f"

    n_pts      = len(plot_df)
    loc_label  = hover or "Locations"
    sample_str = f" ({n_pts:,} sample of {len(clean_df):,})" if sampled else f" ({n_pts:,} locations)"
    title      = f"Map: {loc_label}{agg_label}{sample_str}"

    # ── Figure — use scatter_mapbox (stable, no API token, open-street-map) ───
    try:
        fig = px.scatter_mapbox(
            plot_df,
            lat=lat, lon=lon,
            color=color,
            size=size,
            size_max=22,
            hover_name=hover,
            hover_data=hover_data,
            title=title,
            color_discrete_sequence=pal,
            zoom=zoom,
            center={"lat": centre_lat, "lon": centre_lon},
            mapbox_style="open-street-map",
            opacity=0.82,
        )
    except Exception:
        return []

    # ── Layout ────────────────────────────────────────────────────────────────
    layout = chart_layout(height=520)
    # Remove keys that conflict with map figures
    for key in ("plot_bgcolor", "bargap", "bargroupgap", "xaxis", "yaxis"):
        layout.pop(key, None)
    layout["margin"] = dict(l=0, r=0, t=52, b=0)
    fig.update_layout(**layout)

    if sampled:
        fig.add_annotation(
            text=f"⚠ {n_pts:,}-point sample  —  zoom in for detail",
            xref="paper", yref="paper", x=0.5, y=0.0,
            showarrow=False, xanchor="center", yanchor="bottom",
            font=dict(size=10, color="#f59e0b"),
        )

    charts.append((f"Map: {loc_label}", fig))
    return charts
