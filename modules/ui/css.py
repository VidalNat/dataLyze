"""
modules/ui/css.py -- Global CSS injection and shared UI components.
===================================================================

This module owns everything visual that is shared across pages:
    - inject_css()      -- injects the full Lytrize stylesheet into the page
    - inject_footer()   -- renders the footer bar at the bottom of every page
    - render_logo()     -- renders the top-left logo with a home link
    - render_page_nav() -- renders the top navigation bar (used in analysis/dashboard)

CSS architecture:
    All styles live in a single injected <style> block (no external CSS files).
    The stylesheet uses CSS custom properties (variables) for consistent theming.
    Glassmorphism effect (backdrop-filter: blur) is used for cards and modals.

CONTRIBUTING -- to change the colour theme:
    Edit the :root block at the top of the CSS string in inject_css().
    All component colours reference variables from :root so a single change
    propagates everywhere.

CONTRIBUTING -- to add a new reusable UI component:
    Add a function at the bottom of this file that returns or renders HTML/CSS.
    Use st.markdown(..., unsafe_allow_html=True) to render HTML strings.
    Keep component styles scoped with a unique class prefix to avoid conflicts.

NOTE on unsafe_allow_html:
    Streamlit requires unsafe_allow_html=True to inject custom HTML/CSS.
    This is safe here because all user-supplied content is passed through
    html.escape() before being embedded in any HTML string (see home.py,
    analysis.py). Never embed raw user input without escaping.
"""
"""
modules/ui/css.py
Injects all global styles for Lytrize:
  - Dynamic font system that adapts to browser light/dark mode AND Streamlit theme
  - Modern aurora/mesh gradient background
  - Component styles (cards, buttons, badges, session rows)
  - Footer styles
"""

import base64
from functools import lru_cache
from pathlib import Path

import streamlit as st
from html import escape


BRAND_NAME = "Lytrize"
LOGO_PATH = Path(__file__).resolve().parents[2] / "assets" / "lytrize.ico"


@lru_cache(maxsize=1)
def logo_data_uri() -> str:
    try:
        data = base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")
        return f"data:image/x-icon;base64,{data}"
    except Exception:
        return ""


def inject_css():
    st.markdown("""
    <style>

    /* ═══════════════════════════════════════════════════════════
       FONTS -- dynamic per browser theme
       Uses prefers-color-scheme + Streamlit CSS vars together
       so text is always readable regardless of theme.
    ═══════════════════════════════════════════════════════════ */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Sora:wght@600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

    :root {
        --font-body:  'Inter', system-ui, -apple-system, sans-serif;
        --font-brand: 'Sora', 'Inter', sans-serif;
        --font-mono:  'JetBrains Mono', 'Courier New', monospace;

        /* Light theme tokens */
        --text-primary:   #0f172a;
        --text-secondary: #475569;
        --text-muted:     #94a3b8;
        --surface:        rgba(255,255,255,0.72);
        --surface-hover:  rgba(255,255,255,0.88);
        --border:         rgba(15,23,42,0.10);
        --shadow:         0 4px 24px rgba(15,23,42,0.08);

        /* Brand palette */
        --brand-1: #4f6ef7;
        --brand-2: #8b5cf6;
        --brand-3: #06b6d4;
        --danger:  #ef4444;
        --success: #10b981;
        --warn:    #f59e0b;
    }

    /* Dark theme override using Streamlit's data attribute */
    [data-theme="dark"],
    .stApp[data-theme="dark"] {
        --text-primary:   #f1f5f9;
        --text-secondary: #94a3b8;
        --text-muted:     #64748b;
        --surface:        rgba(15,23,42,0.65);
        --surface-hover:  rgba(30,41,59,0.80);
        --border:         rgba(255,255,255,0.08);
        --shadow:         0 4px 24px rgba(0,0,0,0.35);
    }

    /* Also respond to browser-native dark mode preference */
    @media (prefers-color-scheme: dark) {
        :root {
            --text-primary:   #f1f5f9;
            --text-secondary: #94a3b8;
            --text-muted:     #64748b;
            --surface:        rgba(15,23,42,0.65);
            --surface-hover:  rgba(30,41,59,0.80);
            --border:         rgba(255,255,255,0.08);
            --shadow:         0 4px 24px rgba(0,0,0,0.35);
        }
    }

    html, body, [class*="css"] {
        font-family: var(--font-body) !important;
        color: var(--text-primary) !important;
        -webkit-font-smoothing: antialiased;
    }

    h1, h2, h3, h4, h5, h6 {
        font-family: var(--font-body) !important;
        font-weight: 700;
        letter-spacing: -0.02em;
        color: var(--text-primary) !important;
    }

    code, pre, .stCode {
        font-family: var(--font-mono) !important;
    }

    #MainMenu, footer, header { visibility: hidden; }

    /* ═══════════════════════════════════════════════════════════
       BACKGROUND -- Aurora mesh gradient
       Two layers: a base gradient + animated orbs via pseudo
       Adapts for light (subtle, pastel) and dark (vivid, deep)
    ═══════════════════════════════════════════════════════════ */
    .stApp {
        background:
            radial-gradient(ellipse 80% 60% at 10% 0%,   rgba(79,110,247,0.18) 0%, transparent 60%),
            radial-gradient(ellipse 60% 50% at 90% 10%,  rgba(139,92,246,0.15) 0%, transparent 55%),
            radial-gradient(ellipse 50% 40% at 50% 90%,  rgba(6,182,212,0.12)  0%, transparent 55%),
            radial-gradient(ellipse 70% 60% at 80% 50%,  rgba(245,158,11,0.07) 0%, transparent 60%),
            var(--background-color, #0f172a) !important;
        background-attachment: fixed !important;
    }

    @media (prefers-color-scheme: light) {
        .stApp {
            background:
                radial-gradient(ellipse 80% 60% at 10% 0%,   rgba(79,110,247,0.09) 0%, transparent 60%),
                radial-gradient(ellipse 60% 50% at 90% 10%,  rgba(139,92,246,0.08) 0%, transparent 55%),
                radial-gradient(ellipse 50% 40% at 50% 90%,  rgba(6,182,212,0.07)  0%, transparent 55%),
                #f8faff !important;
            background-attachment: fixed !important;
        }
    }

    /* Mesh noise overlay for texture */
    .stApp::before {
        content: '';
        position: fixed;
        inset: 0;
        background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='0.025'/%3E%3C/svg%3E");
        pointer-events: none;
        z-index: 0;
        opacity: 0.4;
    }

    /* ═══════════════════════════════════════════════════════════
       GLASSMORPHISM SURFACES
    ═══════════════════════════════════════════════════════════ */
    .kpi-card, .metric-card, .ag-card, .sess-card,
    .info-bar, .classifier-box, .themed-box, .glass-card {
        background: var(--surface) !important;
        backdrop-filter: blur(16px) saturate(180%) !important;
        -webkit-backdrop-filter: blur(16px) saturate(180%) !important;
        border: 1px solid var(--border) !important;
        border-radius: 16px !important;
        box-shadow: var(--shadow) !important;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        color: var(--text-primary) !important;
    }
    .kpi-card:hover, .ag-card:hover, .sess-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 32px rgba(79,110,247,0.15) !important;
    }

    .kpi-card { padding: 0.65rem 0.8rem; text-align: center; }
    .kpi-icon { font-size: 1.1rem; margin-bottom: 0.2rem; }
    .kpi-val  { font-family: var(--font-brand); font-size: 1.4rem; font-weight: 800;
                line-height: 1.1; color: var(--text-primary); }
    .kpi-lbl  { font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.1em;
                font-weight: 600; color: var(--text-muted); margin-top: 0.2rem; }

    .ag-card  { padding: 0.8rem 0.7rem; text-align: center; min-height: 90px;
                display: flex; flex-direction: column; align-items: center; justify-content: center; }
    .ag-card.done { border-color: var(--brand-1) !important;
                    box-shadow: 0 0 0 2px rgba(79,110,247,0.25) !important; }
    .ag-icon  { font-size: 1.35rem; margin-bottom: 0.25rem; }
    .ag-name  { font-weight: 700; font-size: 0.8rem; color: var(--text-primary); }
    .ag-desc  { font-size: 0.65rem; color: var(--text-muted); margin-top: 0.18rem; line-height: 1.3; }
    .done-badge { font-size: 0.62rem; background: var(--success); color: #fff;
                  padding: 0.1rem 0.45rem; border-radius: 20px; margin-top: 0.3rem; }

    .sess-card { padding: 0.55rem 0.8rem; }
    .sess-card b { color: var(--text-primary); font-size: 0.88rem; }
    .sess-card small { color: var(--text-muted); font-size: 0.7rem; }

    /* ═══════════════════════════════════════════════════════════
       BRAND & TYPOGRAPHY
    ═══════════════════════════════════════════════════════════ */
    .brand {
        font-family: var(--font-brand);
        font-size: 1.6rem;
        font-weight: 800;
        background: linear-gradient(120deg, var(--brand-1) 20%, var(--brand-2) 80%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        letter-spacing: -0.03em;
    }

    .brand-logo-img {
        width: 1.65rem;
        height: 1.65rem;
        object-fit: contain;
        display: inline-block;
    }

    .sec-label {
        font-size: 0.68rem; font-weight: 700; letter-spacing: 0.12em;
        text-transform: uppercase; color: var(--text-muted); margin: 1.4rem 0 0.7rem;
    }

    /* ═══════════════════════════════════════════════════════════
       WELCOME BANNER
    ═══════════════════════════════════════════════════════════ */
    .welcome-banner {
        background: linear-gradient(135deg,
            rgba(79,110,247,0.90) 0%,
            rgba(139,92,246,0.90) 50%,
            rgba(6,182,212,0.85) 100%);
        backdrop-filter: blur(20px);
        border-radius: 20px;
        padding: 2.2rem 2.5rem;
        margin-bottom: 1.8rem;
        border: 1px solid rgba(255,255,255,0.15);
        box-shadow: 0 8px 40px rgba(79,110,247,0.25);
        position: relative;
        overflow: hidden;
    }
    .welcome-banner::after {
        content: '';
        position: absolute;
        top: -40%; right: -10%;
        width: 350px; height: 350px;
        background: radial-gradient(circle, rgba(255,255,255,0.12) 0%, transparent 70%);
        pointer-events: none;
    }
    .welcome-banner * { color: #fff !important; -webkit-text-fill-color: #fff !important; }

    .pill {
        display: inline-block;
        background: rgba(255,255,255,0.18);
        border: 1px solid rgba(255,255,255,0.30);
        border-radius: 20px;
        padding: 0.28rem 0.85rem;
        font-size: 0.78rem;
        margin: 0.2rem;
        color: #fff;
    }

    /* ═══════════════════════════════════════════════════════════
       BUTTONS
    ═══════════════════════════════════════════════════════════ */
    .stButton > button, .stDownloadButton > button {
        background: linear-gradient(135deg, var(--brand-1), var(--brand-2)) !important;
        color: #fff !important;
        border: none !important;
        border-radius: 10px !important;
        font-family: var(--font-body) !important;
        font-weight: 600 !important;
        font-size: 0.88rem !important;
        letter-spacing: 0.01em !important;
        transition: opacity 0.2s, transform 0.15s, box-shadow 0.2s !important;
        box-shadow: 0 4px 14px rgba(79,110,247,0.30) !important;
    }
    .stButton > button:hover, .stDownloadButton > button:hover {
        opacity: 0.92 !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 20px rgba(79,110,247,0.40) !important;
    }
    .stButton > button:active { transform: translateY(0) !important; }

    /* ═══════════════════════════════════════════════════════════
       FORM INPUTS
    ═══════════════════════════════════════════════════════════ */
    .stTextInput input,
    .stSelectbox div[data-baseweb="select"],
    .stTextArea textarea,
    .stNumberInput input {
        font-family: var(--font-body) !important;
        background: var(--surface) !important;
        backdrop-filter: blur(8px) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border) !important;
        border-radius: 10px !important;
    }
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: var(--brand-1) !important;
        box-shadow: 0 0 0 3px rgba(79,110,247,0.18) !important;
    }

    /* ═══════════════════════════════════════════════════════════
       MISC
    ═══════════════════════════════════════════════════════════ */
    hr { border-top: 1px solid var(--border); }
    .classifier-box { padding: 1rem; }

    /* Edit mode banner */
    .edit-banner {
        background: linear-gradient(135deg, rgba(245,158,11,0.15), rgba(239,68,68,0.10));
        border: 1px solid rgba(245,158,11,0.35);
        border-radius: 12px;
        padding: 0.9rem 1.2rem;
        margin-bottom: 1rem;
        color: var(--text-primary);
    }

    /* ═══════════════════════════════════════════════════════════
       LAYOUT FIXES -- REMOVE STREAMLIT BOTTOM GAP
    ═══════════════════════════════════════════════════════════ */
    .block-container {
        padding-bottom: 0rem !important;
        min-height: calc(100vh - 6rem); 
        display: flex;
        flex-direction: column;
    }
    .block-container > div:first-child {
        flex-grow: 1;
        display: flex;
        flex-direction: column;
    }
    .block-container > div:first-child > div:last-child {
        margin-top: auto;
    }

    </style>
    """, unsafe_allow_html=True)


def render_logo():
    """
    Renders the Lytrize logo at the top of every page (except auth).
    Clicking the logo navigates to the profile/home page.
    """
    token = st.query_params.get("t", "")
    home_url = f"?p=home&nav=home&t={escape(str(token), quote=True)}" if token else "?p=home&nav=home"
    logo_src = logo_data_uri()
    icon_html = (
        f'<img class="brand-logo-img" src="{logo_src}" alt="{BRAND_NAME} logo">'
        if logo_src else '<span style="font-size:1.5rem;line-height:1;">&#128202;</span>'
    )

    st.markdown(
        f'<a href="{home_url}" target="_self" style="text-decoration:none;display:inline-flex;'
        f'align-items:center;gap:6px;cursor:pointer;">'
        f'{icon_html}'
        f'<span class="brand">{BRAND_NAME}</span>'
        f'</a>',
        unsafe_allow_html=True)


def inject_footer():
    """
    Renders the site-wide footer using st.components.v1.html.
    st.markdown strips <svg> tags even with unsafe_allow_html=True.
    components.html renders raw HTML in an iframe, bypassing that sanitiser.
    """
    import streamlit.components.v1 as components
    
    # Inject a spacer div to create the visual gap above the footer
    st.markdown("<div style='margin-top: 5rem;'></div>", unsafe_allow_html=True)
    
    footer_logo = logo_data_uri()
    footer_html = """<!DOCTYPE html>
<html>
<head>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: Inter, system-ui, sans-serif; font-size: 14px; }
.ft { padding: 32px 24px 20px; border-top: 1px solid rgba(128,128,128,0.18); }
.ft-grid { display: grid; grid-template-columns: 2fr 1fr 1fr 1fr; gap: 32px; margin-bottom: 28px; }
@media (prefers-color-scheme: dark) {
  .ft-brand { color: #818cf8; }
  .ft-tagline, .ft-link { color: #94a3b8; }
  .ft-col-title { color: #64748b; }
  .ft-social-btn { background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.1); color: #94a3b8; }
  .ft-social-btn:hover { border-color: #818cf8; color: #818cf8; }
  .ft-badge { background: rgba(79,110,247,0.15); border: 1px solid rgba(79,110,247,0.3); color: #818cf8; }
  .ft-bottom { color: #64748b; border-color: rgba(255,255,255,0.08); }
}
@media (prefers-color-scheme: light) {
  .ft-brand { color: #4f6ef7; }
  .ft-tagline, .ft-link { color: #64748b; }
  .ft-col-title { color: #94a3b8; }
  .ft-social-btn { background: rgba(0,0,0,0.04); border: 1px solid rgba(0,0,0,0.1); color: #64748b; }
  .ft-social-btn:hover { border-color: #4f6ef7; color: #4f6ef7; }
  .ft-badge { background: rgba(79,110,247,0.08); border: 1px solid rgba(79,110,247,0.2); color: #4f6ef7; }
  .ft-bottom { color: #94a3b8; border-color: rgba(0,0,0,0.08); }
}
.ft-brand { font-size: 18px; font-weight: 800; letter-spacing: -0.03em; margin-bottom: 8px; display: inline-flex; align-items: center; gap: 7px; }
.ft-brand img { width: 22px; height: 22px; object-fit: contain; }
.ft-tagline { font-size: 12.5px; line-height: 1.7; margin-bottom: 14px; }
.ft-social { display: flex; gap: 8px; flex-wrap: wrap; }
.ft-social-btn { display: inline-flex; align-items: center; gap: 6px; padding: 5px 12px; border-radius: 8px; font-size: 12px; font-weight: 500; text-decoration: none; transition: border-color .15s, color .15s; }
.ft-col-title { font-size: 10.5px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 12px; }
.ft-link { display: block; font-size: 13px; text-decoration: none; margin-bottom: 8px; transition: color .15s; }
.ft-link:hover { color: #4f6ef7 !important; }
.ft-bottom { display: flex; justify-content: space-between; align-items: center; padding-top: 16px; border-top: 1px solid; font-size: 11.5px; flex-wrap: wrap; gap: 8px; }
.ft-badge { display: inline-block; padding: 2px 9px; border-radius: 20px; font-size: 11px; font-weight: 600; margin-left: 5px; }
</style>
</head>
<body>
<div class="ft">
  <div class="ft-grid">
    <div>
      <div class="ft-brand"><img src="__LYTRIZE_LOGO__" alt="Lytrize logo"> Lytrize</div>
      <div class="ft-tagline">Open-source, browser-based data analysis.<br>Upload. Explore. Share. No code required.</div>
      <div class="ft-social">
        <a class="ft-social-btn" href="https://github.com/VidalNat/dataLyze" target="_blank">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/></svg>
          GitHub
        </a>
        <a class="ft-social-btn" href="https://twitter.com/your-handle" target="_blank">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
          Twitter
        </a>
        <a class="ft-social-btn" href="https://www.linkedin.com/in/vishal-nath/" target="_blank">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 0 1-2.063-2.065 2.064 2.064 0 1 1 2.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>
          LinkedIn
        </a>
      </div>
    </div>
    <div>
      <div class="ft-col-title">Product</div>
      <a class="ft-link" href="https://github.com/VidalNat/dataLyze/wiki" target="_blank">Features</a>
      <a class="ft-link" href="https://github.com/VidalNat/dataLyze/wiki/Roadmap" target="_blank">Roadmap</a>
      <a class="ft-link" href="https://github.com/VidalNat/dataLyze/discussions/categories/change-logs" target="_blank">Changelog</a>
      <a class="ft-link" href="https://github.com/VidalNat/dataLyze/discussions/categories/general" target="_blank">Open Source</a>
    </div>
    <div>
      <div class="ft-col-title">Resources</div>
      <a class="ft-link" href="https://github.com/VidalNat/datalyze/wiki" target="_blank">Documentation</a>
      <a class="ft-link" href="https://github.com/VidalNat/dataLyze/wiki/Getting-started" target="_blank">Getting Started</a>
      <a class="ft-link" href="https://github.com/VidalNat/dataLyze/wiki/Contributing-guide" target="_blank">Contributor Guide</a>
      <a class="ft-link" href="https://github.com/VidalNat/dataLyze/discussions/categories/bug-reports" target="_blank">Report a Bug</a>
    </div>
    <div>
      <div class="ft-col-title">Support</div>
      <a class="ft-link" href="https://github.com/VidalNat/dataLyze/issues/new" target="_blank">Open an Issue</a>
      <a class="ft-link" href="https://github.com/VidalNat/dataLyze/discussions" target="_blank">Discussions</a>
      <a class="ft-link" href="mailto:bantybnath@email.com">Contact Us</a>
      <a class="ft-link" href="https://github.com/VidalNat/dataLyze/discussions/categories/q-a" target="_blank">Get Support</a>
    <!-- <span class="ft-link">&#128241; Android App &#8212; Coming Soon </span> -->
    </div>
  </div>
  <div class="ft-bottom">
    <span>&#169; 2026 Lytrize &nbsp;&#183;&nbsp; MIT License</span>
    <span>Built with &#10084;&#65039; using
      <span class="ft-badge">Streamlit</span>
      <span class="ft-badge">Plotly</span>
      <span class="ft-badge">Python</span>
    </span>
  </div>
</div>
</body>
</html>"""
    components.html(footer_html.replace("__LYTRIZE_LOGO__", footer_logo), height=260, scrolling=False)
    
