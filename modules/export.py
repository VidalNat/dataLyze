"""
modules/export.py - HTML & PDF export engine.
==============================================

Exports the active dashboard as either a standalone HTML file or a PDF.

PDF Architecture (Playwright-based):
    - generate_html_report() builds a self-contained HTML page with embedded
      Plotly charts (interactive JS, full fidelity).
    - generate_pdf_report() feeds that HTML to a headless Chromium browser
      via Playwright, waits for all charts to finish rendering, then prints
      the page to PDF using the browser's native print engine.
    - This approach is cloud-safe: no Kaleido process, no X11, no system
      font dependencies. Works on Streamlit Community Cloud out of the box.

Why not Kaleido?
    Kaleido spawns a sandboxed subprocess which is blocked on Streamlit Cloud
    (and many other PaaS hosts). Charts silently fail → "[Chart unavailable]".

Why not WeasyPrint?
    WeasyPrint does not execute JavaScript, so Plotly charts never render.

CONTRIBUTING:
    To change PDF page size / margins, adjust the `page.pdf(...)` call at
    the bottom of generate_pdf_report().
    To change the visual layout, edit generate_html_report().
"""

import re
import copy
import datetime
import subprocess
import sys
import tempfile
import os
from html import escape
from modules.charts import clean_insight_text

# ── one-time browser-install flag ─────────────────────────────────────────────
_BROWSERS_READY = False


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
                         kpis=None, dashboard_title="", grid_cols_n=2,
                         inline_plotly=False):
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

        # inline_plotly=True embeds the full JS so no CDN fetch is needed
        # (used by PDF path; CDN is fine for the HTML download).
        include_js  = (True if idx == 0 else False) if inline_plotly else ("cdn" if idx == 0 else False)
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


# ── Playwright browser bootstrap ──────────────────────────────────────────────
def _ensure_playwright_browsers() -> None:
    """
    Download the Chromium binary the first time PDF export is called.

    --with-deps is intentionally OMITTED here.
    On Streamlit Community Cloud the app runs as `appuser` (not root), so
    apt-get (which --with-deps invokes) fails with a permission error.
    System-level OS packages are instead declared in packages.txt and
    installed during the build step (as root) before the app starts.

    Locally the same applies: install system deps once via your OS package
    manager; this function only handles the Playwright browser binary.
    """
    global _BROWSERS_READY
    if _BROWSERS_READY:
        return

    # Prefer the `playwright` CLI that lives next to the active Python
    # (i.e. inside the venv bin/).  shutil.which() searches PATH in order,
    # so it finds the venv's binary when the venv is activated.
    # Falling back to `sys.executable -m playwright` handles edge cases where
    # PATH isn't set correctly (e.g. some CI environments).
    import shutil
    pw_cli = shutil.which("playwright")
    cmd = (
        [pw_cli, "install", "chromium"]
        if pw_cli
        else [sys.executable, "-m", "playwright", "install", "chromium"]
    )

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"playwright install chromium failed:\n{result.stderr or result.stdout}"
        )

    _BROWSERS_READY = True


# ── PDF Export — Playwright HTML → PDF ────────────────────────────────────────
def generate_pdf_report(charts, session_name, orientation="portrait",
                        kpis=None, dashboard_title="", grid_cols_n=2):
    """
    Convert the live dashboard to PDF via Playwright (headless Chromium).

    Strategy
    --------
    1. Call generate_html_report() — the same path used by the HTML download
       button, which already produces pixel-perfect, fully interactive output.
    2. Load that HTML into a headless Chromium page.
    3. Wait for Plotly to finish rendering every chart (networkidle + extra
       settle time), then call page.pdf() with the browser's native print
       engine.

    Why this works on Streamlit Cloud
    ----------------------------------
    Kaleido spawns a sandboxed subprocess that the Cloud container blocks.
    Playwright runs Chromium directly without a separate subprocess layer, so
    the sandbox restriction does not apply.
    """
    _ensure_playwright_browsers()

    is_landscape = orientation == "landscape"

    # Build the same HTML the "Download HTML" button produces.
    # inline_plotly=True embeds Plotly JS directly into the HTML so the
    # headless Chromium browser doesn't need to fetch cdn.plot.ly — which
    # is blocked inside Streamlit Cloud containers.
    html_content = generate_html_report(
        charts, session_name,
        orientation=orientation,
        kpis=kpis,
        dashboard_title=dashboard_title,
        grid_cols_n=grid_cols_n,
        inline_plotly=True,
    )

    # Inject print CSS — disable ALL page breaks so the entire dashboard
    # renders as one continuous surface with no pagination.
    print_css = """
    <style>
      @media print {
        body { background: white !important; margin: 0 !important; padding: 1rem !important; }
        * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
        * { break-inside: avoid !important; page-break-inside: avoid !important;
            break-before: avoid !important; break-after: avoid !important; }
      }
    </style>
    """
    html_content = html_content.replace("</head>", print_css + "</head>", 1)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ]
        )
        # Use a tall viewport so Plotly lays out charts at full size
        # before we measure the true rendered height.
        vp_width = 1400 if is_landscape else 1100
        page = browser.new_page(viewport={"width": vp_width, "height": 5000})

        # Step 1 — networkidle: JS is parsed, initial layout pass done.
        page.set_content(html_content, wait_until="networkidle", timeout=60_000)

        # Step 2 — wait until EVERY Plotly chart has produced its <svg>.
        # This is the key fix: a fixed sleep misses slow-rendering charts;
        # polling the DOM catches them all regardless of count or complexity.
        page.wait_for_function(
            """() => {
                const plots = document.querySelectorAll('.js-plotly-plot');
                if (plots.length === 0) return true;
                return Array.from(plots).every(
                    p => p.querySelector('svg.main-svg') !== null
                );
            }""",
            timeout=30_000,
        )

        # Step 3 — scroll to bottom so any deferred/lazy layout is triggered,
        # then give Plotly's relayoutAll a moment to finish resizing.
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1_500)

        # Step 4 — measure the true rendered height of the whole document.
        # We use this to create a single-page PDF sized to fit all content
        # exactly — no blank first page, no overflow pages.
        dims = page.evaluate("""() => ({
            width:  document.documentElement.scrollWidth,
            height: document.documentElement.scrollHeight
        })""")

        pdf_bytes = page.pdf(
            # Custom page size = entire content on one sheet.
            width=f"{dims['width']}px",
            height=f"{dims['height'] + 32}px",  # +32px bottom breathing room
            print_background=True,
            margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
        )
        browser.close()

    return bytes(pdf_bytes)
