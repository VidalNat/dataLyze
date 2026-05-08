"""
modules/analysis/map_plot.py -- Geographic scatter runner.
==========================================================

Plots data points on an interactive map using latitude/longitude columns.
Supports size/metric encoding and colour grouping.

Refinements over v1:
  - Uses px.scatter_map (OpenStreetMap tiles) instead of px.scatter_geo
    → real street-level zoom, no grey globe, draggable and zoomable
  - Auto-zoom: computes bbox of the data and centres the viewport
  - Marker size is scaled proportionally; defaults to a fixed readable size
    when no size column is selected
  - Rich hover: shows location name, lat/lon, and all encoded columns
  - Cluster hint annotation when point count is very high
  - Drop rows with null lat/lon before plotting (avoids marker-at-0,0 bug)
"""
import numpy as np
import pandas as pd
import plotly.express as px
from modules.charts import chart_layout, COLORS
from modules.utils.perf import sample_for_plot


def _auto_zoom(lats, lons) -> tuple[float, float, int]:
    """
    Return (centre_lat, centre_lon, zoom_level) that fits all points.
    Zoom logic mirrors Mapbox's tile zoom levels.
    """
    try:
        lat_range = float(np.max(lats) - np.min(lats))
        lon_range = float(np.max(lons) - np.min(lons))
        spread    = max(lat_range, lon_range)
        if   spread > 120: zoom = 1
        elif spread > 60:  zoom = 2
        elif spread > 30:  zoom = 3
        elif spread > 15:  zoom = 4
        elif spread > 7:   zoom = 5
        elif spread > 3:   zoom = 6
        elif spread > 1.5: zoom = 7
        elif spread > 0.7: zoom = 8
        elif spread > 0.3: zoom = 9
        elif spread > 0.1: zoom = 10
        else:              zoom = 11
        return float(np.mean(lats)), float(np.mean(lons)), zoom
    except Exception:
        return 20.0, 0.0, 2


def run_map_plot(df, lat_col=None, lon_col=None, size_col=None, color_col=None,
                 location_col=None, palette=None, **kwargs):
    charts = []
    pal    = palette or COLORS

    # ── Auto-detect lat/lon columns ───────────────────────────────────────────
    lat = lat_col or next((c for c in df.columns if "lat" in c.lower()), None)
    lon = lon_col or next(
        (c for c in df.columns if "lon" in c.lower() or "lng" in c.lower() or "long" in c.lower()),
        None,
    )
    num = [c for c in df.select_dtypes("number").columns]
    lat = lat or (num[0] if num else None)
    lon = lon or (num[1] if len(num) > 1 else None)

    if not lat or not lon or lat not in df.columns or lon not in df.columns:
        return []

    # ── Drop rows where lat or lon is null/zero-zeroed (common import artifact)
    needed = [lat, lon]
    for c in (size_col, color_col, location_col):
        if c and c in df.columns:
            needed.append(c)
    clean_df = df[needed].dropna(subset=[lat, lon]).copy()
    # Remove the classic (0, 0) sentinel — it usually means "no GPS fix"
    clean_df = clean_df[~((clean_df[lat] == 0) & (clean_df[lon] == 0))]
    if clean_df.empty:
        return []

    # ── Sample for performance ────────────────────────────────────────────────
    plot_df, sampled = sample_for_plot(clean_df, n=20_000)

    # ── Validate optional encoding columns ────────────────────────────────────
    size  = size_col  if size_col  and size_col  in plot_df.columns else None
    color = color_col if color_col and color_col in plot_df.columns else None
    hover = location_col if location_col and location_col in plot_df.columns else None

    # ── Auto-zoom ─────────────────────────────────────────────────────────────
    centre_lat, centre_lon, zoom = _auto_zoom(plot_df[lat], plot_df[lon])

    # ── Build title ───────────────────────────────────────────────────────────
    loc_label  = hover or "Locations"
    sample_str = f"  (20 K sample of {len(clean_df):,})" if sampled else ""
    title      = f"Map: {loc_label}{sample_str}"

    # ── Hover columns: show whatever is encoded ───────────────────────────────
    hover_data = {}
    for col in (size, color):
        if col and col != hover:
            hover_data[col] = True
    hover_data[lat] = ":.5f"
    hover_data[lon] = ":.5f"

    fig = px.scatter_map(
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
        map_style="open-street-map",
    )

    fig.update_traces(
        marker=dict(
            opacity=0.80,
            sizemin=4,   # minimum visible dot size even when no size col
        ) if not size else dict(opacity=0.75, sizemin=4),
    )

    layout = chart_layout()
    layout.pop("plot_bgcolor", None)   # map tiles need transparent bg
    fig.update_layout(
        **layout,
        margin=dict(l=0, r=0, t=48, b=0),
    )

    if sampled:
        fig.add_annotation(
            text=f"⚠ 20 K-point sample of {len(clean_df):,} total rows",
            xref="paper", yref="paper", x=0.5, y=1.0,
            showarrow=False, xanchor="center", yanchor="bottom",
            font=dict(size=10, color="#f59e0b"),
        )

    charts.append((f"Map: {loc_label}", fig))
    return charts
