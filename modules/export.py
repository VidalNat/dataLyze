"""
modules/export.py - PDF export engine.
========================================

Generates a single-page PDF report from the active dashboard charts.

Architecture:
    - Uses the fpdf2 library (not reportlab) for PDF generation.
    - Page height is computed dynamically before the PDF is created so all
      charts fit on ONE page without overflow. auto_page_break is disabled.
    - Each chart is rasterised to PNG via Plotly kaleido renderer, then
      embedded into the PDF as an image.
    - Insight text is wrapped and rendered below each chart.
    - A fixed header (title, file name, date) and footer (page number) are
      added after all chart content.

Bug fix applied:
    set_auto_page_break(auto=False): previously True, which caused fpdf to
    insert blank overflow pages even though PAGE_H was pre-calculated to
    fit all content exactly.

CONTRIBUTING - to change the layout:
    Adjust MARGIN, CHART_H, TEXT_LINE_H constants near the top of the file.
    PAGE_W is fixed at A4 width; PAGE_H grows to fit content.
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
                         kpis=None, dashboard_title="", grid_cols_n=2):
    is_landscape = orientation == "landscape"
    max_width    = "1400px" if is_landscape else "1100px"
    # Use grid_cols_n for the CSS grid; full-width items span all columns
    grid_css_cols = f"repeat({grid_cols_n}, 1fr)"
    title        = dashboard_title or session_name
    safe_title   = _h(title)

    # KPI strip
    kpi_html = ""
    if kpis:
        change_style = lambda k: (
            f'color:{"#10b981" if k.get("change_pct",0)>=0 else "#ef4444"};font-weight:700'
            if "change_pct" in k else "")
        arrow = lambda k: ("▲ " if k.get("change_pct",0)>=0 else "▼ ") if "change_pct" in k else ""

        def _kpi_val_style(k, base_change):
            full = f'{k.get("prefix","")}{k.get("value","--")}{k.get("suffix","")}'
            size = "0.95rem" if len(full) > 16 else ("1.1rem" if len(full) > 12 else "1.4rem")
            wrap = "white-space:normal;word-break:break-word;overflow-wrap:anywhere;" if len(full) > 12 else ""
            return f"font-size:{size};{wrap}{base_change}"

        kpi_items = "".join(
            f'<div class="kpi-card">'
            f'<div class="kpi-icon">{_h(k.get("icon","📊"))}</div>'
            f'<div class="kpi-value" style="{_kpi_val_style(k, change_style(k))}">'
            f'{_h(arrow(k))}{_h(k.get("prefix",""))}{_h(k.get("value","--"))}{_h(k.get("suffix",""))}</div>'
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

        display_title = meta.get("custom_title") or chart_title
        subtitle      = meta.get("subtitle", "")
        is_full       = meta.get("full_width", False)
        # Span all columns when full-width
        col_span      = f"grid-column: 1 / -1;" if is_full else ""

        # Make figure responsive -- clear the embedded title (rendered via <h2> below)
        fig_resp = copy.deepcopy(fig)
        fig_resp.update_layout(title_text="")   # title shown as <h2>, not inside chart
        is_horiz = any(getattr(t, "orientation", "v") == "h"
                       for t in fig_resp.data if hasattr(t, "orientation"))
        if is_horiz:
            fig_resp.update_yaxes(tickfont=dict(size=11), automargin=True)
            fig_resp.update_xaxes(tickfont=dict(size=11))
            fig_resp.update_layout(margin=dict(l=130, r=30, t=20, b=30))
        else:
            fig_resp.update_xaxes(tickangle=-35, tickfont=dict(size=11), automargin=True)
            fig_resp.update_yaxes(tickfont=dict(size=11), automargin=True)
            fig_resp.update_layout(margin=dict(l=30, r=30, t=20, b=80))
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

        notes_str  = str(notes).strip() if notes else ""
        notes_html = (
            f'<div class="notes"><strong>Analysis Notes:</strong> {_h(notes_str)}</div>'
            if notes_str else ""
        )

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
  <title>{safe_title} -- Lytrize</title>
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
                 box-shadow: 0 2px 12px rgba(0,0,0,0.07); min-width: 130px; flex: 1; max-width: 220px; }}
    .kpi-icon  {{ font-size: 1.4rem; margin-bottom: 0.25rem; }}
    .kpi-value {{ font-size: 1.4rem; font-weight: 800; color: #4f6ef7; line-height: 1.2;
                  overflow: visible; }}
    .kpi-label {{ font-size: 0.72rem; color: #64748b; margin-top: 0.2rem; font-weight: 600;
                  text-transform: uppercase; letter-spacing: 0.06em; }}
    hr {{ border: none; border-top: 1px solid #e2e8f0; margin: 1.5rem 0; }}
    .grid {{
      display: grid;
      grid-template-columns: {grid_css_cols};
      gap: 1.5rem;
      width: 100%;
    }}
    .chart-card {{
      background: white;
      border-radius: 14px;
      padding: 1.2rem;
      box-shadow: 0 2px 16px rgba(0,0,0,0.07);
      min-width: 0;
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
      <div class="meta">Generated by Lytrize &middot; {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
    </div>
    {kpi_html}
    <div class="grid">{chart_blocks}</div>
  </div>
  <script>
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


# ── PDF Export -- single-page dashboard layout ─────────────────────────────────
def generate_pdf_report(charts, session_name, orientation="portrait",
                        kpis=None, dashboard_title="", grid_cols_n=2):
    """
    Renders all charts on one or more pages in a grid matching grid_cols_n.
    Page breaks automatically when content overflows.
    """
    title        = dashboard_title or session_name
    is_landscape = orientation == "landscape"

    # ── Page geometry ─────────────────────────────────────────────────────────
    PAGE_W   = 297.0 if is_landscape else 210.0
    PAGE_H_A = 210.0 if is_landscape else 297.0   # standard A4 height
    MARGIN   = 14.0
    COL_GAP  = 6.0
    EFF_W    = PAGE_W - 2 * MARGIN
    # For portrait always use 1 col; for landscape use the grid setting
    N_COLS   = grid_cols_n if is_landscape else 1
    COL_W    = (EFF_W - COL_GAP * (N_COLS - 1)) / N_COLS
    CHART_H  = round(COL_W * 9 / 16, 1)   # 16:9 aspect per chart image

    n_charts = len(charts)
    n_rows   = math.ceil(n_charts / N_COLS) if n_charts > 0 else 1

    TITLE_H      = 8.0   # chart title text + optional subtitle
    NOTE_H       = 5.0   # notes line below image
    INSIGHT_H    = 13.0  # up to 3 auto-insight lines
    ROW_CONTENT  = TITLE_H + CHART_H + NOTE_H + INSIGHT_H
    ROW_GAP      = 10.0
    ROW_H        = ROW_CONTENT + ROW_GAP

    HEADER_H     = 24.0
    KPI_H        = 32.0 if kpis else 0
    FOOTER_H     = 12.0
    # Add 20mm buffer so last row never clips against footer
    content_h = MARGIN + HEADER_H + KPI_H + n_rows * ROW_H + FOOTER_H + MARGIN + 20.0
    PAGE_H    = max(PAGE_H_A, content_h)

    # ── Render chart PNGs ─────────────────────────────────────────────────────
    PX_W = int(COL_W * 5)
    PX_H = int(CHART_H * 5)
    chart_imgs = []
    for item in charts:
        uid, chart_title, fig, notes = item[:4]
        meta = item[6] if len(item) > 6 else {}
        fig_copy = copy.deepcopy(fig)
        xl = meta.get("x_label", ""); yl = meta.get("y_label", "")
        if xl: fig_copy.update_xaxes(title_text=xl)
        if yl: fig_copy.update_yaxes(title_text=yl)
        disp = meta.get("custom_title") or chart_title
        # Remove chart title from image -- drawn as text above in PDF
        fig_copy.update_layout(title_text="")
        is_horiz = any(getattr(t, "orientation", "v") == "h"
                       for t in fig_copy.data if hasattr(t, "orientation"))
        if is_horiz:
            fig_copy.update_yaxes(tickfont=dict(size=9), automargin=True)
            fig_copy.update_xaxes(tickfont=dict(size=9))
            fig_copy.update_layout(margin=dict(l=120, r=16, t=10, b=16))
        else:
            fig_copy.update_xaxes(tickangle=-35, tickfont=dict(size=9), automargin=True)
            fig_copy.update_yaxes(tickfont=dict(size=9), automargin=True)
            fig_copy.update_layout(margin=dict(l=16, r=16, t=10, b=64))
        fig_copy.update_layout(paper_bgcolor="white", plot_bgcolor="white")
        try:
            raw = pio.to_image(fig_copy, format="png",
                               width=PX_W, height=PX_H, scale=2)
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            tmp.write(bytes(raw)); tmp.close()
            chart_imgs.append({
                "path":     tmp.name,
                "title":    disp,
                "subtitle": meta.get("subtitle", ""),
                "notes":    str(notes).strip() if notes else "",
                "insights": item[4] if len(item) > 4 else [],
                "meta":     meta,
                "full_w":   meta.get("full_width", False),
            })
        except Exception as e:
            chart_imgs.append({"path": None, "title": chart_title,
                               "subtitle": "", "notes": f"[render error: {e}]",
                               "insights": [], "meta": meta, "full_w": False})

    # ── Build PDF ─────────────────────────────────────────────────────────────
    pdf = FPDF(orientation="L" if is_landscape else "P",
               unit="mm", format=(PAGE_W, PAGE_H))
    pdf.set_margins(MARGIN, MARGIN, MARGIN)
    # auto_page_break as safety net -- if content somehow exceeds PAGE_H it won't clip
    pdf.set_auto_page_break(auto=False)  # FIX: PAGE_H is pre-calculated; True caused blank overflow pages.
    pdf.add_page()

    y = MARGIN  # current Y cursor

    # ── Header ────────────────────────────────────────────────────────────────
    pdf.set_xy(MARGIN, y)
    pdf.set_font("helvetica", "B", 16)
    pdf.set_text_color(79, 110, 247)
    pdf.cell(EFF_W, 8, _clean_pdf(title), align="C",
             new_x="LMARGIN", new_y="NEXT")
    y += 9

    pdf.set_xy(MARGIN, y)
    pdf.set_font("helvetica", "", 7)
    pdf.set_text_color(100, 116, 139)
    sub = _clean_pdf(
        f"Generated by Lytrize  \u00b7  "
        f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    pdf.cell(EFF_W, 4, sub, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    y += 6

    pdf.set_draw_color(226, 232, 240)
    pdf.line(MARGIN, y, MARGIN + EFF_W, y)
    y += 5

    # ── KPI row ───────────────────────────────────────────────────────────────
    if kpis:
        n_kpi = len(kpis)
        kpi_w = min(44.0, EFF_W / n_kpi)
        kpi_x0 = MARGIN + (EFF_W - kpi_w * n_kpi) / 2
        BOX_H = 18.0

        for ki, k in enumerate(kpis):
            kx = kpi_x0 + ki * kpi_w
            # Card background
            pdf.set_fill_color(240, 244, 255)
            pdf.set_draw_color(200, 210, 250)
            pdf.rect(kx, y, kpi_w - 2, BOX_H, style="FD")

            # Icon
            pdf.set_xy(kx, y + 1.5)
            pdf.set_font("helvetica", "", 8)
            pdf.set_text_color(100, 116, 139)
            pdf.cell(kpi_w - 2, 4, _clean_pdf(k.get("icon", "")), align="C")

            # Value
            pdf.set_xy(kx, y + 6)
            pdf.set_font("helvetica", "B", 9)
            change = k.get("change_pct")
            if change is not None:
                color = (16, 185, 129) if change >= 0 else (239, 68, 68)
            else:
                color = (79, 110, 247)
            pdf.set_text_color(*color)
            val_str = _clean_pdf(
                f'{k.get("prefix","")}{k.get("value","")}{k.get("suffix","")}')
            pdf.cell(kpi_w - 2, 5, val_str, align="C")

            # Label
            pdf.set_xy(kx, y + 12)
            pdf.set_font("helvetica", "", 5.5)
            pdf.set_text_color(100, 116, 139)
            pdf.cell(kpi_w - 2, 3.5, _clean_pdf(k.get("label", "")), align="C")

        pdf.set_text_color(0, 0, 0)
        y += BOX_H + 4
        pdf.set_draw_color(226, 232, 240)
        pdf.line(MARGIN, y, MARGIN + EFF_W, y)
        y += 5

    # ── Charts ────────────────────────────────────────────────────────────────
    x_positions = [MARGIN + i * (COL_W + COL_GAP) for i in range(N_COLS)]

    for row_i in range(n_rows):
        start_i = row_i * N_COLS
        indices  = list(range(start_i, min(start_i + N_COLS, len(chart_imgs))))

        row_y = y

        for slot, ci in enumerate(indices):
            info  = chart_imgs[ci]
            is_fw = info["full_w"]
            xpos  = x_positions[slot]
            cw    = EFF_W if is_fw else COL_W

            # Chart title
            pdf.set_xy(xpos, row_y)
            pdf.set_font("helvetica", "B", 8)
            pdf.set_text_color(30, 41, 59)
            # Clip long titles to one line
            t_clip = _clean_pdf(info["title"])[:72]
            pdf.cell(cw, 5, t_clip, align="L")

            sub_offset = 0
            if info["subtitle"]:
                pdf.set_xy(xpos, row_y + 5)
                pdf.set_font("helvetica", "I", 6)
                pdf.set_text_color(100, 116, 139)
                pdf.cell(cw, 3.5, _clean_pdf(info["subtitle"]), align="L")
                sub_offset = 3.5

            img_y = row_y + 5 + sub_offset + 1

            if info["path"]:
                pdf.image(info["path"], x=xpos, y=img_y,
                          w=EFF_W if is_fw else COL_W, h=CHART_H)
                try:
                    os.remove(info["path"])
                except Exception:
                    pass
            else:
                pdf.set_fill_color(248, 250, 252)
                pdf.rect(xpos, img_y, cw, CHART_H, style="F")
                pdf.set_xy(xpos, img_y + CHART_H / 2 - 3)
                pdf.set_font("helvetica", "I", 7)
                pdf.set_text_color(148, 163, 184)
                pdf.cell(cw, 5, "[Chart unavailable]", align="C")

            # Auto-insights directly below chart image
            pdf.set_text_color(0, 0, 0)
            after_img_y = img_y + CHART_H + 1
            insights = info.get("insights", [])
            meta_i   = info.get("meta", {})
            ins_end_y = after_img_y
            if insights and meta_i.get("show_auto_insights", True):
                hidden  = set(meta_i.get("hidden_insights", []))
                visible = [ins for i, ins in enumerate(insights) if i not in hidden]
                if visible:
                    ins_y = after_img_y
                    pdf.set_font("helvetica", "", 5.5)
                    pdf.set_text_color(79, 110, 247)
                    max_chars_ins = int(cw / 1.55)
                    for ins in visible[:3]:   # cap at 3 lines
                        txt = _clean_pdf(clean_insight_text(ins))
                        if len(txt) > max_chars_ins:
                            txt = txt[:max_chars_ins - 1] + "..."
                        pdf.set_xy(xpos, ins_y)
                        pdf.cell(cw, 4.0, f"- {txt}", align="L")
                        ins_y += 4.0
                    ins_end_y = ins_y

            # Notes below insights
            notes_str = info.get("notes", "")
            if notes_str and info["path"]:
                note_y = ins_end_y + 0.5
                pdf.set_xy(xpos, note_y)
                pdf.set_font("helvetica", "I", 6)
                pdf.set_text_color(130, 80, 200)
                label = "Notes: "
                full  = _clean_pdf(f"{label}{notes_str}")
                max_chars = int(cw / 1.8)
                if len(full) > max_chars:
                    full = full[:max_chars - 1] + "..."
                pdf.cell(cw, 3.5, full, align="L")

            pdf.set_text_color(0, 0, 0)

            if is_fw:
                break  # full-width chart occupies entire row

        y += ROW_H

    # ── Footer ────────────────────────────────────────────────────────────────
    # Anchor to bottom of page rather than using the accumulated y cursor,
    # so it always appears regardless of how much content was rendered above.
    footer_y = PAGE_H - MARGIN - 6
    pdf.set_xy(MARGIN, footer_y)
    pdf.set_draw_color(226, 232, 240)
    pdf.line(MARGIN, footer_y, MARGIN + EFF_W, footer_y)
    pdf.set_xy(MARGIN, footer_y + 2)
    pdf.set_font("helvetica", "", 6)
    pdf.set_text_color(148, 163, 184)
    pdf.cell(EFF_W, 4, _clean_pdf(f"Lytrize  \u00b7  {title}"), align="C")

    return bytes(pdf.output())
