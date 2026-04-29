"""
modules/export.py
HTML and PDF report exports.

HTML:  Full interactive report with responsive Plotly charts.
PDF:   Single-page dashboard screenshot — all charts on ONE page in a
       2-column grid, sized to fit content (custom tall page if needed).
"""

import os
import re
import copy
import json
import math
import datetime
import tempfile
import plotly.io as pio
from fpdf import FPDF
from html import escape
from modules.charts import clean_insight_text


# ── Emoji / encoding helpers ──────────────────────────────────────────────────
_EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FFFF"
    "\U00002500-\U00002BFF"
    "\U00002100-\U000024FF"
    "\u2600-\u26FF"
    "\u2700-\u27BF"
    "]+", flags=re.UNICODE)

_ICON_MAP = {
    "💰": "$", "📊": "[chart]", "📐": "[med]", "🔢": "#",
    "⬇️": "v", "⬆️": "^", "📈": "%", "🔍": "[?]",
    "📅": "[dt]", "🏆": "1st", "📉": "[low]",
    "💡": "*", "📝": "Note:", "•": "-",
}

def _clean_pdf(text: str) -> str:
    s = str(text)
    for em, rep in _ICON_MAP.items():
        s = s.replace(em, rep)
    s = _EMOJI_RE.sub("", s)
    return s.encode("latin-1", "replace").decode("latin-1")


def _h(text) -> str:
    return escape(str(text), quote=True)


# ── HTML Export ───────────────────────────────────────────────────────────────
def generate_html_report(charts, session_name, orientation="portrait",
                         kpis=None, dashboard_title=""):
    is_landscape = orientation == "landscape"
    max_width    = "1400px" if is_landscape else "1100px"
    grid_cols    = "repeat(2, 1fr)" if is_landscape else "1fr"
    title        = dashboard_title or session_name
    safe_title   = _h(title)

    # KPI strip
    kpi_html = ""
    if kpis:
        change_style = lambda k: (
            f'color:{"#10b981" if k.get("change_pct",0)>=0 else "#ef4444"};font-weight:700'
            if "change_pct" in k else "")
        arrow = lambda k: ("▲ " if k.get("change_pct",0)>=0 else "▼ ") if "change_pct" in k else ""
        kpi_items = "".join(
            f'<div class="kpi-card">'
            f'<div class="kpi-icon">{_h(k.get("icon","📊"))}</div>'
            f'<div class="kpi-value" style="{change_style(k)}">'
            f'{_h(arrow(k))}{_h(k.get("prefix",""))}{_h(k.get("value","—"))}{_h(k.get("suffix",""))}</div>'
            f'<div class="kpi-label">{_h(k.get("label","KPI"))}</div>'
            f'</div>'
            for k in kpis
        )
        kpi_html = f'<div class="kpi-row">{kpi_items}</div><hr>'

    # Chart blocks
    chart_blocks = ""
    for idx, item in enumerate(charts):
        uid, chart_title, fig, notes = item[:4]
        auto_insights = item[4] if len(item) > 4 else []
        meta          = item[6] if len(item) > 6 else {}

        display_title  = meta.get("custom_title") or chart_title
        subtitle       = meta.get("subtitle", "")
        col_assignment = meta.get("col", 1)
        col_span       = "grid-column: 1 / -1;" if col_assignment == 3 or meta.get("full_width") else ""

        # Make figure responsive and fix axis readability
        fig_resp = copy.deepcopy(fig)
        fig_resp.update_layout(title_text=_h(display_title))
        is_horiz = any(getattr(t, "orientation", "v") == "h"
                       for t in fig_resp.data if hasattr(t, "orientation"))
        if is_horiz:
            fig_resp.update_yaxes(tickfont=dict(size=11), automargin=True)
            fig_resp.update_xaxes(tickfont=dict(size=11))
            fig_resp.update_layout(margin=dict(l=130, r=30, t=50, b=30))
        else:
            fig_resp.update_xaxes(tickangle=-35, tickfont=dict(size=11), automargin=True)
            fig_resp.update_yaxes(tickfont=dict(size=11), automargin=True)
            fig_resp.update_layout(margin=dict(l=30, r=30, t=50, b=80))
        fig_resp.update_layout(autosize=True, width=None, height=400,
                               paper_bgcolor="white", plot_bgcolor="white")

        include_js  = "cdn" if idx == 0 else False
        chart_html  = fig_resp.to_html(full_html=False, include_plotlyjs=include_js,
                                       config={"responsive": True})

        insight_html = ""
        if auto_insights and meta.get("show_auto_insights", True):
            hidden  = set(meta.get("hidden_insights", []))
            visible = [ins for i, ins in enumerate(auto_insights) if i not in hidden]
            if visible:
                items_html = "".join(f"<li>{_h(clean_insight_text(ins))}</li>" for ins in visible)
                insight_html = (f'<div class="insights"><strong>Insights</strong>'
                                f'<ul>{items_html}</ul></div>')

        notes_html = f'<div class="notes"><strong>Analysis Notes:</strong> {_h(notes)}</div>' if notes else ""

        chart_blocks += (
            f'<div class="chart-card" style="{col_span}">'
            f'<h2>{_h(display_title)}</h2>'
            + (f'<p class="subtitle">{_h(subtitle)}</p>' if subtitle else "")
            + f'<div class="chart-wrap">{chart_html}</div>'
            + insight_html + notes_html
            + '</div>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{safe_title} — Lytrize</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Inter', sans-serif; padding: 2rem; background: #f8fafc; color: #0f172a; }}
    .wrapper {{ max-width: {max_width}; margin: auto; width: 100%; }}
    .report-header {{ text-align: center; margin-bottom: 2rem; }}
    .report-header h1 {{ font-size: 2rem; font-weight: 800; color: #4f6ef7; }}
    .report-header .meta {{ font-size: 0.8rem; color: #64748b; margin-top: 0.4rem; }}
    .kpi-row {{ display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 1.5rem; justify-content: center; }}
    .kpi-card {{ background: white; border-radius: 12px; padding: 1rem 1.4rem; text-align: center;
                 box-shadow: 0 2px 12px rgba(0,0,0,0.07); min-width: 130px; flex: 1; max-width: 200px; }}
    .kpi-icon  {{ font-size: 1.4rem; margin-bottom: 0.25rem; }}
    .kpi-value {{ font-size: 1.4rem; font-weight: 800; color: #4f6ef7; }}
    .kpi-label {{ font-size: 0.72rem; color: #64748b; margin-top: 0.2rem; font-weight: 600;
                  text-transform: uppercase; letter-spacing: 0.06em; }}
    hr {{ border: none; border-top: 1px solid #e2e8f0; margin: 1.5rem 0; }}
    .grid {{
      display: grid;
      grid-template-columns: {grid_cols};
      gap: 1.5rem;
      width: 100%;
    }}
    .chart-card {{
      background: white;
      border-radius: 14px;
      padding: 1.2rem;
      box-shadow: 0 2px 16px rgba(0,0,0,0.07);
      min-width: 0;        /* critical: prevents card overflowing grid cell */
      width: 100%;
      overflow: hidden;
    }}
    .chart-card h2 {{ font-size: 0.95rem; font-weight: 700; margin-bottom: 0.15rem; color: #1e293b; }}
    .subtitle {{ font-size: 0.78rem; color: #64748b; margin-bottom: 0.6rem; }}
    .chart-wrap {{
      width: 100%;
      overflow: hidden;
      display: block;
    }}
    /* Force Plotly SVG/canvas to fill full card width */
    .chart-wrap .js-plotly-plot {{ width: 100% !important; display: block !important; }}
    .chart-wrap .plotly        {{ width: 100% !important; }}
    .chart-wrap .plot-container {{ width: 100% !important; }}
    .chart-wrap svg.main-svg   {{ width: 100% !important; }}
    .insights {{ background: #f0f4ff; border-left: 3px solid #4f6ef7; border-radius: 6px;
                 padding: 0.6rem 0.9rem; margin-top: 0.7rem; font-size: 0.8rem; }}
    .insights strong {{ display: block; margin-bottom: 0.25rem; }}
    .insights ul {{ margin-left: 1rem; }}
    .insights li {{ margin-bottom: 0.2rem; line-height: 1.5; }}
    .notes {{ background: #fdf4ff; padding: 0.6rem 0.9rem; border-left: 4px solid #8b5cf6;
              margin-top: 0.7rem; border-radius: 4px; font-size: 0.82rem; font-style: italic; }}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="report-header">
      <h1>&#128202; {safe_title}</h1>
      <div class="meta">Generated by Lytrize &middot; {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}
        &middot; {orientation.title()} layout</div>
    </div>
    {kpi_html}
    <div class="grid">{chart_blocks}</div>
  </div>
  <script>
    /* Relayout all Plotly charts to fill their container on load and resize */
    function relayoutAll() {{
      if (typeof Plotly === 'undefined') return;
      document.querySelectorAll('.js-plotly-plot').forEach(function(el) {{
        try {{
          var w = el.closest('.chart-wrap');
          var width = w ? w.offsetWidth : el.offsetWidth;
          if (width > 0) Plotly.relayout(el, {{width: width, autosize: true}});
        }} catch(e) {{}}
      }});
    }}
    window.addEventListener('load', function() {{ setTimeout(relayoutAll, 200); }});
    window.addEventListener('resize', function() {{ setTimeout(relayoutAll, 100); }});
  </script>
</body>
</html>"""


# ── PDF Export — single-page dashboard layout ─────────────────────────────────
def generate_pdf_report(charts, session_name, orientation="portrait",
                        kpis=None, dashboard_title=""):
    """
    Renders ALL charts on a SINGLE page in a 2-column grid, like a dashboard
    screenshot.  The page height is calculated to fit every element; minimum
    is A4 height (297 mm portrait / 210 mm landscape).
    """
    title = dashboard_title or session_name
    is_landscape = orientation == "landscape"

    # ── Page geometry ─────────────────────────────────────────────────────────
    PAGE_W  = 297.0 if is_landscape else 210.0
    MARGIN  = 12.0
    COL_GAP = 8.0
    EFF_W   = PAGE_W - 2 * MARGIN
    N_COLS  = 2 if is_landscape else 1
    COL_W   = (EFF_W - COL_GAP * (N_COLS - 1)) / N_COLS
    CHART_H = round(COL_W * 9 / 16, 1)   # 16:9 aspect per chart image

    n_charts = len(charts)
    n_rows   = math.ceil(n_charts / N_COLS) if n_charts > 0 else 1
    ROW_H    = CHART_H + 20   # chart + title text + small gap

    # Section heights
    HEADER_H  = 24.0
    KPI_H     = (14 + len(kpis or []) * 0) + 8 if kpis else 0  # drawn as 1 row of boxes
    KPI_BOX_H = 18.0 if kpis else 0
    CHART_SEC = n_rows * ROW_H
    FOOTER_H  = 8.0

    PAGE_H = max(210.0 if is_landscape else 297.0,
                 MARGIN + HEADER_H + KPI_H + KPI_BOX_H + CHART_SEC + FOOTER_H + MARGIN)

    # ── Render chart PNGs ─────────────────────────────────────────────────────
    PX_W  = int(COL_W * 5)          # ~5 px per mm → crisp at 127 DPI-equivalent
    PX_H  = int(CHART_H * 5)
    chart_imgs = []
    for item in charts:
        uid, chart_title, fig, notes = item[:4]
        meta = item[6] if len(item) > 6 else {}
        fig_copy = copy.deepcopy(fig)
        xl = meta.get("x_label", ""); yl = meta.get("y_label", "")
        if xl: fig_copy.update_xaxes(title_text=xl)
        if yl: fig_copy.update_yaxes(title_text=yl)
        disp = meta.get("custom_title") or chart_title
        # Axis readability: angle x-ticks for vertical charts, expand margins
        is_horiz = any(getattr(t, "orientation", "v") == "h"
                       for t in fig_copy.data if hasattr(t, "orientation"))
        if is_horiz:
            fig_copy.update_yaxes(tickfont=dict(size=9), automargin=True)
            fig_copy.update_xaxes(tickfont=dict(size=9))
            fig_copy.update_layout(margin=dict(l=120, r=20, t=44, b=20))
        else:
            fig_copy.update_xaxes(tickangle=-35, tickfont=dict(size=9), automargin=True)
            fig_copy.update_yaxes(tickfont=dict(size=9), automargin=True)
            fig_copy.update_layout(margin=dict(l=20, r=20, t=44, b=70))
        fig_copy.update_layout(title_text=disp,
                               paper_bgcolor="white", plot_bgcolor="white")
        try:
            raw = pio.to_image(fig_copy, format="png", width=PX_W, height=PX_H, scale=2)
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            tmp.write(bytes(raw)); tmp.close()
            chart_imgs.append({
                "path":    tmp.name,
                "title":   disp,
                "subtitle": meta.get("subtitle", ""),
                "notes":   notes or "",
                "insights": item[4] if len(item) > 4 else [],
                "meta":    meta,
            })
        except Exception as e:
            chart_imgs.append({"path": None, "title": chart_title,
                               "subtitle": "", "notes": f"[render error: {e}]",
                               "insights": [], "meta": meta})

    # ── Build PDF ─────────────────────────────────────────────────────────────
    pdf = FPDF(orientation="L" if is_landscape else "P", unit="mm", format=(PAGE_W, PAGE_H))
    pdf.set_margins(MARGIN, MARGIN, MARGIN)
    pdf.set_auto_page_break(auto=False)   # single page — we control layout
    pdf.add_page()

    y = MARGIN  # current Y cursor

    def _text(txt, size=10, style="", align="L", w=None, h=6, newline=True):
        nonlocal y
        pdf.set_xy(MARGIN, y)
        pdf.set_font("helvetica", style, size)
        pdf.cell(w or EFF_W, h, _clean_pdf(txt), align=align,
                 new_x="LMARGIN" if newline else "RIGHT",
                 new_y="NEXT"    if newline else "TOP")
        if newline:
            y += h

    # Header
    _text(title, size=18, style="B", align="C", h=10)
    pdf.set_xy(MARGIN, y)
    pdf.set_font("helvetica", "", 8)
    pdf.set_text_color(100, 116, 139)
    sub_line = _clean_pdf(
        f"Generated by Lytrize  \u00b7  "
        f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}  \u00b7  Dashboard")
    pdf.cell(EFF_W, 5, sub_line, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    y += 7
    pdf.set_draw_color(226, 232, 240)
    pdf.line(MARGIN, y, MARGIN + EFF_W, y)
    y += 5

    # KPI row (all KPIs side-by-side in one band)
    if kpis:
        kpi_w    = min(50, EFF_W / len(kpis))
        kpi_x0   = MARGIN + (EFF_W - kpi_w * len(kpis)) / 2
        BOX_H    = 16
        for ki, k in enumerate(kpis):
            kx = kpi_x0 + ki * kpi_w
            pdf.set_fill_color(240, 244, 255)
            pdf.rect(kx, y, kpi_w - 2, BOX_H, style="F")
            pdf.set_xy(kx, y + 2)
            pdf.set_font("helvetica", "B", 10)
            pdf.set_text_color(79, 110, 247)
            change = k.get("change_pct")
            val_str = _clean_pdf(
                f'{k.get("prefix","")}{k.get("value","")}{k.get("suffix","")}')
            if change is not None:
                arrow = "+" if change >= 0 else ""
                val_str = _clean_pdf(f"{arrow}{change:.1f}%")
            pdf.cell(kpi_w - 2, 6, val_str, align="C")
            pdf.set_xy(kx, y + 9)
            pdf.set_font("helvetica", "", 6)
            pdf.set_text_color(100, 116, 139)
            pdf.cell(kpi_w - 2, 4, _clean_pdf(k.get("label","")), align="C")
        pdf.set_text_color(0, 0, 0)
        y += BOX_H + 5
        pdf.set_draw_color(226, 232, 240)
        pdf.line(MARGIN, y, MARGIN + EFF_W, y)
        y += 5

    # Charts
    for row_i in range(n_rows):
        start_i = row_i * N_COLS

        x_positions = [MARGIN + i * (COL_W + COL_GAP) for i in range(N_COLS)]
        indices = [i for i in range(start_i, min(start_i + N_COLS, len(chart_imgs)))]

        # Chart title row (small, above the image)
        row_y = y  # remember row start

        for slot, ci in enumerate(indices):
            info = chart_imgs[ci]
            xpos = x_positions[slot]

            # Title above chart
            pdf.set_xy(xpos, row_y)
            pdf.set_font("helvetica", "B", 8)
            pdf.set_text_color(30, 41, 59)
            pdf.cell(COL_W, 5, _clean_pdf(info["title"]), align="L")
            if info["subtitle"]:
                pdf.set_xy(xpos, row_y + 5)
                pdf.set_font("helvetica", "I", 6)
                pdf.set_text_color(100, 116, 139)
                pdf.cell(COL_W, 4, _clean_pdf(info["subtitle"]), align="L")

            img_y = row_y + (9 if info["subtitle"] else 6)

            if info["path"]:
                pdf.image(info["path"], x=xpos, y=img_y, w=COL_W, h=CHART_H)
                try:
                    os.remove(info["path"])
                except Exception:
                    pass
            else:
                # Placeholder box for failed render
                pdf.set_fill_color(248, 250, 252)
                pdf.rect(xpos, img_y, COL_W, CHART_H, style="F")
                pdf.set_xy(xpos, img_y + CHART_H / 2 - 3)
                pdf.set_font("helvetica", "I", 7)
                pdf.set_text_color(100, 116, 139)
                pdf.cell(COL_W, 5, _clean_pdf(info["notes"]), align="C")

            # Notes below chart
            note_y = img_y + CHART_H + 1
            pdf.set_text_color(0, 0, 0)
            if info["notes"] and info["path"]:
                pdf.set_xy(xpos, note_y)
                pdf.set_font("helvetica", "I", 6)
                pdf.set_text_color(100, 116, 139)
                note_clean = _clean_pdf(info["notes"])[:90]
                pdf.cell(COL_W, 3.5, f"Analysis Notes: {note_clean}", align="L")

        pdf.set_text_color(0, 0, 0)
        y += ROW_H   # advance to next row

    # Footer
    pdf.set_xy(MARGIN, PAGE_H - MARGIN - 4)
    pdf.set_font("helvetica", "", 6)
    pdf.set_text_color(148, 163, 184)
    pdf.cell(EFF_W, 4, _clean_pdf(f"Lytrize  ·  {title}"), align="C")

    return bytes(pdf.output())
