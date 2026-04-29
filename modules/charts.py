"""
modules/charts.py
Chart colour palettes, layout defaults, Plotly serialisation, and the
auto-insight engine. Import from here in any analysis module.
"""

import json
import re
import streamlit as st
import pandas as pd
import plotly.io as pio

COLORS = ["#4f6ef7","#8b5cf6","#06b6d4","#f59e0b","#ef4444","#10b981","#ec4899","#f97316"]
DANGER = ["#bbf7d0","#fbbf24","#ef4444"]

PALETTES = {
    "🔵 Default Blue-Purple": ["#4f6ef7","#8b5cf6","#06b6d4","#f59e0b","#ef4444","#10b981","#ec4899","#f97316"],
    "🌈 Vibrant":             ["#e63946","#f4a261","#2a9d8f","#457b9d","#e9c46a","#264653","#a8dadc","#f1faee"],
    "🍃 Nature Green":        ["#2d6a4f","#40916c","#52b788","#74c69d","#95d5b2","#b7e4c7","#d8f3dc","#1b4332"],
    "🌅 Warm Sunset":         ["#e76f51","#f4a261","#e9c46a","#264653","#2a9d8f","#e63946","#f1faee","#457b9d"],
    "🩷 Pink & Coral":        ["#ff6b6b","#feca57","#48dbfb","#ff9ff3","#54a0ff","#5f27cd","#01abc6","#ff9f43"],
    "🌊 Ocean Blues":         ["#03045e","#0077b6","#00b4d8","#90e0ef","#caf0f8","#023e8a","#0096c7","#ade8f4"],
    "🟣 Monochrome Purple":   ["#3c096c","#5a189a","#7b2fbe","#9d4edd","#c77dff","#e0aaff","#240046","#10002b"],
    "🔆 Pastel Light":        ["#ffadad","#ffd6a5","#fdffb6","#caffbf","#9bf6ff","#a0c4ff","#bdb2ff","#ffc6ff"],
}


def chart_layout():
    return dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=48, b=20),
        bargap=0.28,
        bargroupgap=0.1,
    )


def num_cols():
    return st.session_state.get("num_cols", [])

def cat_cols():
    return st.session_state.get("cat_cols", [])

def dt_cols():
    return st.session_state.get("dt_cols", [])


def clean_insight_text(text) -> str:
    """Return display/export-safe plain insight text, including legacy Markdown cleanup."""
    s = str(text or "")
    s = re.sub(r"\*\*(.*?)\*\*", r"\1", s)
    s = s.replace("__", "")
    s = s.replace("  ·  ", " · ")
    return s.strip()


def clean_insights(insights) -> list[str]:
    return [s for s in (clean_insight_text(i) for i in (insights or [])) if s]


def _fmt_num(value) -> str:
    try:
        v = float(value)
    except Exception:
        return str(value)
    if pd.isna(v):
        return "n/a"
    sign = "-" if v < 0 else ""
    av = abs(v)
    if av >= 1_000_000_000:
        return f"{sign}{av / 1_000_000_000:.1f}B"
    if av >= 1_000_000:
        return f"{sign}{av / 1_000_000:.1f}M"
    if av >= 1_000:
        return f"{sign}{av / 1_000:.1f}K"
    if av == int(av):
        return f"{int(v):,}"
    return f"{v:,.2f}"


def _fmt_pct(value) -> str:
    try:
        return f"{float(value):+.1f}%"
    except Exception:
        return "n/a"


def _plural(count, singular: str, plural: str = None) -> str:
    return singular if int(count) == 1 else (plural or f"{singular}s")


def _fmt_label(value) -> str:
    try:
        ts = pd.to_datetime(value, errors="coerce")
        if pd.notna(ts):
            if ts.hour or ts.minute or ts.second:
                return ts.strftime("%d %b %Y %H:%M")
            return ts.strftime("%d %b %Y")
    except Exception:
        pass
    return str(value)


def _as_number_series(values) -> pd.Series:
    return pd.to_numeric(pd.Series(values), errors="coerce").dropna()


def _as_list(values) -> list:
    if values is None:
        return []
    try:
        return list(values)
    except Exception:
        return []


# ── Serialisation (extended format with insights & meta) ──────────────────────
def charts_to_json(charts):
    out = []
    for chart in charts:
        uid, title, fig = chart[:3]
        desc          = st.session_state.get(f"desc_{uid}", "")
        auto_insights = clean_insights(st.session_state.get(f"auto_insights_{uid}", []))
        chart_type    = st.session_state.get(f"chart_type_{uid}", "")
        meta          = st.session_state.get(f"chart_meta_{uid}", {})
        try:
            out.append({
                "uid":          uid,
                "title":        title,
                "fig_json":     pio.to_json(fig),
                "desc":         desc,
                "auto_insights": auto_insights,
                "chart_type":   chart_type,
                "meta":         meta,
            })
        except Exception:
            pass
    return json.dumps(out)


# ── Auto-insight engine ───────────────────────────────────────────────────────
def generate_chart_insights(chart_type: str, title: str, fig,
                             col_descriptions: dict = None) -> list:
    insights = []
    tl = title.lower()

    if chart_type == "distribution" or "dist:" in tl:
        try:
            arr = _as_number_series(fig.data[0].x)
            if arr.empty:
                return []
            mean, median, std = arr.mean(), arr.median(), arr.std()
            skew = float(arr.skew())
            insights.append(
                f"Typical value is around {_fmt_num(median)}. The average is {_fmt_num(mean)}, "
                f"and the usual spread is about {_fmt_num(std)}."
            )
            if abs(skew) > 1:
                if skew > 0:
                    insights.append(
                        "A few high values are pulling the average upward, so the median is the safer everyday benchmark."
                    )
                else:
                    insights.append(
                        "A few low values are pulling the average downward, so compare decisions against the median too."
                    )
            else:
                insights.append("Values are fairly balanced around the middle, so the average and median tell a similar story.")
            q1, q3 = arr.quantile(0.25), arr.quantile(0.75)
            iqr = q3 - q1
            n_out = ((arr < q1-1.5*iqr) | (arr > q3+1.5*iqr)).sum()
            if n_out > 0:
                insights.append(
                    f"{n_out:,} {_plural(n_out, 'unusual value')} "
                    f"{'sits' if n_out == 1 else 'sit'} outside the normal range. "
                    "Review them before trusting totals or averages."
                )
        except Exception:
            pass

    elif chart_type == "correlation" or "correlation" in tl:
        try:
            z = fig.data[0].z
            x_labels = _as_list(getattr(fig.data[0], "x", None))
            y_labels = _as_list(getattr(fig.data[0], "y", None)) or x_labels
            if z is not None:
                best = None
                for r, row in enumerate(z):
                    for c, val in enumerate(row):
                        if r == c or val is None:
                            continue
                        try:
                            fv = float(val)
                        except Exception:
                            continue
                        if abs(fv) >= 1:
                            continue
                        if best is None or abs(fv) > abs(best[0]):
                            left = str(y_labels[r]) if r < len(y_labels) else f"Column {r+1}"
                            right = str(x_labels[c]) if c < len(x_labels) else f"Column {c+1}"
                            best = (fv, left, right)
                if best:
                    strength = "strong" if abs(best[0]) >= 0.7 else "moderate" if abs(best[0]) >= 0.4 else "weak"
                    direction = "move in the same direction" if best[0] > 0 else "move in opposite directions"
                    insights.append(
                        f"{best[1]} and {best[2]} show the clearest relationship: {strength}, "
                        f"{direction} ({best[0]:.2f})."
                    )
                else:
                    insights.append("No clear relationship stands out between the selected numeric columns.")
            insights.append("Use this as a clue for investigation, not proof that one column causes another.")
        except Exception:
            pass

    elif chart_type == "outlier" or "outlier" in tl:
        try:
            outlier_trace = next((t for t in fig.data if "outlier" in str(getattr(t, "name", "")).lower()), None)
            if outlier_trace and len(outlier_trace.y) > 0:
                n = len(outlier_trace.y)
                vals = _as_number_series(outlier_trace.y)
                if not vals.empty:
                    insights.append(
                        f"{n:,} {_plural(n, 'unusual value')} "
                        f"{'was' if n == 1 else 'were'} found, ranging from "
                        f"{_fmt_num(vals.min())} to {_fmt_num(vals.max())}."
                    )
                else:
                    insights.append(f"{n:,} {_plural(n, 'unusual value')} {'was' if n == 1 else 'were'} found.")
                if n > 10:
                    insights.append("The count is high, so check for data-entry issues or a different scale before summarising.")
                else:
                    insights.append("Review these rows individually; a single unusual value can distort averages and trends.")
            else:
                insights.append("No obvious outliers were found using the usual range check.")
        except Exception:
            pass

    elif chart_type == "time_series" or "ts:" in tl or "trend" in tl:
        try:
            y = _as_number_series(fig.data[0].y)
            if len(y) >= 2:
                trend = "increased" if y.iloc[-1] > y.iloc[0] else "decreased" if y.iloc[-1] < y.iloc[0] else "stayed flat"
                pct = (y.iloc[-1] - y.iloc[0]) / abs(y.iloc[0]) * 100 if y.iloc[0] != 0 else 0
                insights.append(
                    f"The trend {trend} from {_fmt_num(y.iloc[0])} to {_fmt_num(y.iloc[-1])} "
                    f"({_fmt_pct(pct)} from start to end)."
                )
                peak_i = int(y.reset_index(drop=True).idxmax())
                low_i = int(y.reset_index(drop=True).idxmin())
                x_vals = _as_list(getattr(fig.data[0], "x", None))
                peak_x = f" at {_fmt_label(x_vals[peak_i])}" if peak_i < len(x_vals) else ""
                low_x = f" at {_fmt_label(x_vals[low_i])}" if low_i < len(x_vals) else ""
                insights.append(
                    f"Highest point is {_fmt_num(y.max())}{peak_x}; lowest point is {_fmt_num(y.min())}{low_x}."
                )
        except Exception:
            pass
        insights.append("Look for repeating peaks or dips; those often point to seasonality or operating patterns.")

    elif chart_type in ("categorical", "pie_chart") or any(k in tl for k in ("count", "bar", "pie", "donut")):
        try:
            data = fig.data[0]
            # For horizontal bar charts orientation='h': x=values, y=categories
            is_horiz = getattr(data, "orientation", "v") == "h"
            if is_horiz:
                vals = [v for v in _as_list(getattr(data, "x", None)) if v is not None]
                xs   = _as_list(getattr(data, "y", None))
            elif hasattr(data, "y") and data.y is not None and not isinstance(data.y[0] if len(data.y) else 0, str):
                vals = [v for v in _as_list(data.y) if v is not None]
                xs   = _as_list(getattr(data, "x", None))
            elif hasattr(data, "values") and data.values is not None:
                vals = _as_list(data.values); xs = _as_list(getattr(data, "labels", None))
            else:
                # Fallback: try x as values if y looks like strings
                vals = [v for v in _as_list(getattr(data, "x", None)) if isinstance(v, (int, float))]
                xs   = _as_list(getattr(data, "y", None))
            if vals:
                vals = [float(v) for v in vals]
                total = sum(v for v in vals if v)
                top_i = vals.index(max(vals))
                top_cat = xs[top_i] if xs and top_i < len(xs) else str(top_i)
                top_pct = (max(vals) / total * 100) if total else 0
                insights.append(
                    f"{top_cat} leads with {_fmt_num(max(vals))}, which is {top_pct:.1f}% of the values shown."
                )
                n_cats = len(vals)
                if n_cats > 1:
                    sorted_vals = sorted(vals, reverse=True)
                    if len(sorted_vals) > 1 and sorted_vals[1] and sorted_vals[0] / sorted_vals[1] >= 1.1:
                        insights.append(
                            f"The leader is {sorted_vals[0] / sorted_vals[1]:.1f}x the next largest category."
                        )
                    even_pct = 100 / n_cats
                    concentration = max(vals) / total * 100
                    if concentration > 2 * even_pct:
                        insights.append("The result is concentrated, so this category has an outsized effect on the total.")
                    else:
                        insights.append(f"The values are reasonably balanced across {n_cats} categories.")
        except Exception:
            pass

    elif chart_type == "statistical" or any(k in tl for k in ("mean", "std", "min", "max")):
        try:
            data = fig.data[0]
            vals = _as_number_series(getattr(data, "y", []))
            labels = _as_list(getattr(data, "x", None))
            if not vals.empty:
                top_i = int(vals.reset_index(drop=True).idxmax())
                top_label = labels[top_i] if top_i < len(labels) else "The highest item"
                insights.append(f"{top_label} is the highest value in this chart at {_fmt_num(vals.max())}.")
                if vals.min() != vals.max():
                    insights.append(
                        f"The range runs from {_fmt_num(vals.min())} to {_fmt_num(vals.max())}, "
                        "so compare the largest and smallest items before drawing conclusions."
                    )
        except Exception:
            pass
        if not insights:
            insights.append("Compare the largest and smallest values first; they usually explain the main story.")

    elif chart_type == "data_quality" or any(k in tl for k in ("missing", "duplicate", "quality")):
        try:
            data = fig.data[0]
            if hasattr(data, "labels") and hasattr(data, "values"):
                labels = list(data.labels)
                vals = [float(v) for v in data.values]
                total = sum(vals)
                details = []
                for label, val in zip(labels, vals):
                    pct = val / total * 100 if total else 0
                    details.append(f"{label}: {_fmt_num(val)} ({pct:.1f}%)")
                if details:
                    insights.append("Data quality split — " + "; ".join(details) + ".")
        except Exception:
            pass
        insights.append("Clean missing or duplicate rows before using these charts for decisions.")

    if col_descriptions:
        for col, desc in col_descriptions.items():
            if col.lower() in tl and desc.strip():
                insights.append(f"Context: {col} means {desc.strip()}")

    return clean_insights(insights)
