"""
modules/ui/css.py -- Global CSS injection and shared UI components.
"""
import base64
from functools import lru_cache
from pathlib import Path

import streamlit as st
from html import escape

BRAND_NAME = "Lytrize"
LOGO_PATH  = Path(__file__).resolve().parents[2] / "assets" / "lytrize.ico"


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
/* ── Google Fonts ─────────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Sora:wght@700;800&family=JetBrains+Mono:wght@400;500&display=swap');

/* ── Design tokens ────────────────────────────────────────────────────── */
:root {
  --font-body:  'Inter', system-ui, -apple-system, sans-serif;
  --font-brand: 'Sora', 'Inter', sans-serif;
  --font-mono:  'JetBrains Mono', monospace;

  --brand-1: #4f6ef7;
  --brand-2: #8b5cf6;
  --brand-3: #06b6d4;
  --danger:  #ef4444;
  --success: #10b981;
  --warn:    #f59e0b;

  /* Light */
  --bg:             #f0f4ff;
  --surface:        rgba(255,255,255,0.82);
  --surface-hover:  rgba(255,255,255,0.96);
  --surface-raised: rgba(255,255,255,0.95);
  --border:         rgba(79,110,247,0.12);
  --border-soft:    rgba(15,23,42,0.07);
  --text-primary:   #0f172a;
  --text-secondary: #475569;
  --text-muted:     #94a3b8;
  --shadow-sm:      0 1px 3px rgba(15,23,42,0.07), 0 1px 2px rgba(15,23,42,0.04);
  --shadow-md:      0 4px 16px rgba(15,23,42,0.08), 0 1px 4px rgba(15,23,42,0.04);
  --shadow-lg:      0 8px 40px rgba(79,110,247,0.12), 0 2px 8px rgba(15,23,42,0.06);
  --shadow-brand:   0 4px 20px rgba(79,110,247,0.28);
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 18px;
  --radius-xl: 24px;
  --transition: all 0.2s cubic-bezier(0.4,0,0.2,1);
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg:             #080d1a;
    --surface:        rgba(15,23,42,0.72);
    --surface-hover:  rgba(22,33,60,0.90);
    --surface-raised: rgba(18,28,50,0.95);
    --border:         rgba(79,110,247,0.18);
    --border-soft:    rgba(255,255,255,0.06);
    --text-primary:   #f1f5f9;
    --text-secondary: #94a3b8;
    --text-muted:     #475569;
    --shadow-sm:      0 1px 3px rgba(0,0,0,0.3);
    --shadow-md:      0 4px 16px rgba(0,0,0,0.35);
    --shadow-lg:      0 8px 40px rgba(0,0,0,0.45), 0 2px 8px rgba(79,110,247,0.12);
  }
}
[data-theme="dark"],:root[data-theme="dark"] {
  --bg:             #080d1a;
  --surface:        rgba(15,23,42,0.72);
  --surface-hover:  rgba(22,33,60,0.90);
  --surface-raised: rgba(18,28,50,0.95);
  --border:         rgba(79,110,247,0.18);
  --border-soft:    rgba(255,255,255,0.06);
  --text-primary:   #f1f5f9;
  --text-secondary: #94a3b8;
  --text-muted:     #475569;
  --shadow-sm:      0 1px 3px rgba(0,0,0,0.3);
  --shadow-md:      0 4px 16px rgba(0,0,0,0.35);
  --shadow-lg:      0 8px 40px rgba(0,0,0,0.45), 0 2px 8px rgba(79,110,247,0.12);
}

/* ── Reset & base ─────────────────────────────────────────────────────── */
html,body,[class*="css"]{font-family:var(--font-body)!important;-webkit-font-smoothing:antialiased;color:var(--text-primary)!important;}
h1,h2,h3,h4,h5,h6{font-family:var(--font-body)!important;font-weight:700;letter-spacing:-0.02em;color:var(--text-primary)!important;}
code,pre,.stCode{font-family:var(--font-mono)!important;}
#MainMenu,footer,header{visibility:hidden;}
*{box-sizing:border-box;}

/* ── Page background ──────────────────────────────────────────────────── */
.stApp {
  background:
    radial-gradient(ellipse 75% 55% at 5%  0%,  rgba(79,110,247,0.16) 0%, transparent 55%),
    radial-gradient(ellipse 55% 45% at 95% 5%,  rgba(139,92,246,0.14) 0%, transparent 50%),
    radial-gradient(ellipse 45% 40% at 50% 95%, rgba(6,182,212,0.11)  0%, transparent 50%),
    radial-gradient(ellipse 65% 55% at 80% 55%, rgba(245,158,11,0.05) 0%, transparent 55%),
    var(--bg) !important;
  background-attachment: fixed !important;
}
/* Subtle noise texture */
.stApp::before{content:'';position:fixed;inset:0;background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.022'/%3E%3C/svg%3E");pointer-events:none;z-index:0;opacity:.35;}

/* ── Page entry animation ─────────────────────────────────────────────── */
@keyframes fadeUp {
  from { opacity:0; transform:translateY(14px); }
  to   { opacity:1; transform:translateY(0);    }
}
@keyframes fadeIn {
  from { opacity:0; } to { opacity:1; }
}
@keyframes pulse-ring {
  0%   { transform:scale(1);   opacity:.7; }
  50%  { transform:scale(1.05);opacity:1;  }
  100% { transform:scale(1);   opacity:.7; }
}
.block-container > div > div {
  animation: fadeUp 0.35s cubic-bezier(0.4,0,0.2,1) both;
}

/* ── Layout ───────────────────────────────────────────────────────────── */
.block-container {
  padding-top: 1.2rem !important;
  padding-bottom: 0 !important;
  max-width: 1380px !important;
  padding-left: 2.5rem !important;
  padding-right: 2.5rem !important;
}

/* ── TOP NAVBAR ───────────────────────────────────────────────────────── */
.ly-navbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: .55rem 1rem .55rem .5rem;
  background: var(--surface);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  margin-bottom: 1.4rem;
  gap: 1rem;
}
.ly-navbar-brand {
  display:inline-flex; align-items:center; gap:7px;
  text-decoration:none; flex-shrink:0;
}
.ly-navbar-brand img { width:1.55rem; height:1.55rem; object-fit:contain; }
.ly-navbar-brand .brand { font-family:var(--font-brand); font-size:1.35rem; font-weight:800;
  background:linear-gradient(120deg,var(--brand-1) 20%,var(--brand-2) 80%);
  -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text;
  letter-spacing:-0.03em; }
.ly-navbar-links { display:flex; align-items:center; gap:.4rem; flex-wrap:wrap; }
.ly-nav-btn {
  display:inline-flex; align-items:center; gap:.35rem;
  padding:.38rem .85rem; border-radius:var(--radius-sm);
  font-size:.82rem; font-weight:600; cursor:pointer;
  border:1px solid var(--border-soft);
  background:transparent; color:var(--text-secondary);
  transition:var(--transition); text-decoration:none; white-space:nowrap;
}
.ly-nav-btn:hover { background:var(--surface-hover); color:var(--text-primary); border-color:var(--brand-1); }
.ly-nav-btn.active { background:rgba(79,110,247,.12); color:var(--brand-1); border-color:var(--brand-1); }

/* ── PAGE NAV STEPS (upload → analysis → dashboard) ──────────────────── */
.ly-steps {
  display:flex; align-items:center; gap:0;
  background:var(--surface);
  border:1px solid var(--border-soft);
  border-radius: var(--radius-lg);
  padding:.35rem .5rem;
  box-shadow:var(--shadow-sm);
  margin-bottom:1.4rem;
  overflow:hidden;
}
.ly-step {
  display:flex; align-items:center; gap:.45rem;
  padding:.42rem 1rem; border-radius: var(--radius-md);
  font-size:.8rem; font-weight:600; color:var(--text-muted);
  transition:var(--transition); white-space:nowrap; cursor:default;
}
.ly-step.done  { color:var(--success); }
.ly-step.active{ background:linear-gradient(135deg,var(--brand-1),var(--brand-2));
                  color:#fff; box-shadow:var(--shadow-brand); }
.ly-step-sep   { color:var(--text-muted); font-size:.75rem; padding:0 .1rem; opacity:.4; }
.ly-step .step-num { width:1.4rem;height:1.4rem;border-radius:50%;background:rgba(255,255,255,.2);
  display:inline-flex;align-items:center;justify-content:center;font-size:.7rem;font-weight:800; }
.ly-step.done .step-num { background:var(--success); color:#fff; }

/* ── GLASS CARDS ──────────────────────────────────────────────────────── */
.glass-card,.kpi-card,.ag-card,.sess-card,.info-bar,.classifier-box,.themed-box,.metric-card {
  background: var(--surface) !important;
  backdrop-filter: blur(16px) saturate(180%) !important;
  -webkit-backdrop-filter: blur(16px) saturate(180%) !important;
  border: 1px solid var(--border-soft) !important;
  border-radius: var(--radius-lg) !important;
  box-shadow: var(--shadow-md) !important;
  transition: var(--transition);
  color: var(--text-primary) !important;
}
.glass-card:hover,.ag-card:hover,.sess-card:hover {
  transform:translateY(-2px);
  box-shadow:var(--shadow-lg) !important;
  border-color:var(--border) !important;
}

/* ── KPI CARDS ────────────────────────────────────────────────────────── */
.kpi-card { padding:.9rem 1rem; text-align:center; border-radius:var(--radius-lg)!important; }
.kpi-icon { font-size:1.4rem; margin-bottom:.3rem; }
.kpi-val  { font-family:var(--font-brand); font-size:1.65rem; font-weight:800;
             line-height:1.1; color:var(--text-primary); }
.kpi-lbl  { font-size:.65rem; text-transform:uppercase; letter-spacing:.1em;
             font-weight:700; color:var(--text-muted); margin-top:.25rem; }

/* ── ANALYSIS GRID CARDS ──────────────────────────────────────────────── */
.ag-card  { padding:.9rem .75rem; text-align:center; min-height:96px;
             display:flex;flex-direction:column;align-items:center;justify-content:center; }
.ag-card.done { border-color:var(--brand-1)!important;
                 box-shadow:0 0 0 2px rgba(79,110,247,.22)!important; }
.ag-icon  { font-size:1.45rem; margin-bottom:.28rem; }
.ag-name  { font-weight:700; font-size:.82rem; color:var(--text-primary); }
.ag-desc  { font-size:.67rem; color:var(--text-muted); margin-top:.18rem; line-height:1.35; }
.done-badge { font-size:.63rem; background:var(--success); color:#fff;
               padding:.1rem .5rem; border-radius:20px; margin-top:.35rem; font-weight:600; }

/* ── SESSION CARDS ────────────────────────────────────────────────────── */
.sess-card { padding:.75rem 1rem; }
.sess-card b { color:var(--text-primary); font-size:.9rem; }
.sess-card small { color:var(--text-muted); font-size:.72rem; }

/* ── WELCOME BANNER ───────────────────────────────────────────────────── */
.welcome-banner {
  background: linear-gradient(135deg, rgba(79,110,247,.88) 0%, rgba(139,92,246,.88) 55%, rgba(6,182,212,.82) 100%);
  backdrop-filter: blur(24px);
  border-radius: var(--radius-xl);
  padding: 2rem 2.4rem;
  margin-bottom: 1.6rem;
  border: 1px solid rgba(255,255,255,.14);
  box-shadow: 0 8px 48px rgba(79,110,247,.22), 0 1px 0 rgba(255,255,255,.1) inset;
  position: relative; overflow: hidden;
}
.welcome-banner::before {
  content:'';position:absolute;top:-60%;right:-8%;width:380px;height:380px;
  background:radial-gradient(circle,rgba(255,255,255,.11) 0%,transparent 68%);pointer-events:none;
}
.welcome-banner::after {
  content:'';position:absolute;bottom:-40%;left:-5%;width:260px;height:260px;
  background:radial-gradient(circle,rgba(6,182,212,.15) 0%,transparent 65%);pointer-events:none;
}
.welcome-banner * { color:#fff!important; -webkit-text-fill-color:#fff!important; }

/* ── BRAND ────────────────────────────────────────────────────────────── */
.brand {
  font-family:var(--font-brand);font-size:1.5rem;font-weight:800;
  background:linear-gradient(120deg,var(--brand-1) 20%,var(--brand-2) 80%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
  letter-spacing:-0.03em;
}
.brand-logo-img { width:1.55rem;height:1.55rem;object-fit:contain;display:inline-block; }
.sec-label { font-size:.68rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;
               color:var(--text-muted);margin:1.4rem 0 .7rem; }
.pill { display:inline-block;background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.28);
         border-radius:20px;padding:.26rem .8rem;font-size:.78rem;margin:.2rem;color:#fff; }

/* ── AUTH CARD ────────────────────────────────────────────────────────── */
.auth-card {
  background: var(--surface-raised);
  backdrop-filter: blur(24px) saturate(200%);
  -webkit-backdrop-filter: blur(24px) saturate(200%);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-xl);
  padding: 2.4rem 2rem 2rem;
  box-shadow: var(--shadow-lg), 0 1px 0 rgba(255,255,255,.08) inset;
  animation: fadeUp .4s cubic-bezier(0.4,0,0.2,1) both;
}
.auth-tab-row { display:flex; gap:.5rem; margin-bottom:1.5rem; }
.auth-tab {
  flex:1; padding:.5rem; border-radius:var(--radius-md);
  font-size:.85rem; font-weight:600; text-align:center; cursor:pointer;
  border:1px solid var(--border-soft); background:transparent; color:var(--text-muted);
  transition:var(--transition);
}
.auth-tab.active {
  background:linear-gradient(135deg,var(--brand-1),var(--brand-2));
  color:#fff; border-color:transparent; box-shadow:var(--shadow-brand);
}
.auth-tab:hover:not(.active) { background:var(--surface-hover); color:var(--text-primary); }

/* ── BUTTONS ──────────────────────────────────────────────────────────── */
.stButton > button, .stDownloadButton > button {
  background: linear-gradient(135deg, var(--brand-1), var(--brand-2)) !important;
  color: #fff !important;
  border: none !important;
  border-radius: var(--radius-md) !important;
  font-family: var(--font-body) !important;
  font-weight: 600 !important;
  font-size: .81rem !important;
  letter-spacing: .01em !important;
  transition: var(--transition) !important;
  box-shadow: 0 2px 8px rgba(79,110,247,.2) !important;
  padding: .32rem .85rem !important;
  line-height: 1.35 !important;
  min-height: unset !important;
  white-space: nowrap !important;
}
.stButton > button:hover,.stDownloadButton > button:hover {
  opacity:.9 !important; transform:translateY(-1px) !important;
  box-shadow: 0 4px 14px rgba(79,110,247,.32) !important;
}
.stButton > button:active { transform:translateY(0)!important; box-shadow:none!important; }
/* Secondary buttons */
.stButton > button[kind="secondary"] {
  background: var(--surface) !important;
  color: var(--text-secondary) !important;
  border: 1px solid var(--border-soft) !important;
  box-shadow: var(--shadow-sm) !important;
}
.stButton > button[kind="secondary"]:hover {
  background: var(--surface-hover) !important;
  color: var(--text-primary) !important;
  border-color: var(--brand-1) !important;
}

/* ── INPUTS ───────────────────────────────────────────────────────────── */
.stTextInput input,
.stTextArea textarea,
.stNumberInput input,
.stSelectbox div[data-baseweb="select"],
.stMultiSelect div[data-baseweb="select"] {
  font-family: var(--font-body) !important;
  background: var(--surface) !important;
  backdrop-filter: blur(8px) !important;
  color: var(--text-primary) !important;
  border: 1px solid var(--border-soft) !important;
  border-radius: var(--radius-md) !important;
  transition: var(--transition) !important;
}
.stTextInput input:focus,.stTextArea textarea:focus {
  border-color: var(--brand-1) !important;
  box-shadow: 0 0 0 3px rgba(79,110,247,.15) !important;
  outline: none !important;
}
label, .stTextInput label, .stSelectbox label, .stTextArea label {
  font-size: .8rem !important;
  font-weight: 600 !important;
  color: var(--text-secondary) !important;
  letter-spacing: .01em !important;
}

/* ── DATAFRAME ────────────────────────────────────────────────────────── */
.stDataFrame { border-radius: var(--radius-md) !important; overflow: hidden; box-shadow: var(--shadow-sm); }
.stDataFrame table { font-size: .82rem !important; }
.stDataFrame thead { background: linear-gradient(135deg,rgba(79,110,247,.08),rgba(139,92,246,.06)) !important; }

/* ── EXPANDERS ────────────────────────────────────────────────────────── */
.streamlit-expanderHeader {
  border-radius: var(--radius-md) !important;
  font-weight: 600 !important;
  font-size: .88rem !important;
  transition: var(--transition) !important;
}
.streamlit-expanderHeader:hover { background: var(--surface-hover) !important; }
.streamlit-expanderContent {
  border: 1px solid var(--border-soft) !important;
  border-top: none !important;
  border-radius: 0 0 var(--radius-md) var(--radius-md) !important;
  padding: 1rem !important;
}

/* ── SELECTBOX ────────────────────────────────────────────────────────── */
[data-baseweb="popover"] { border-radius: var(--radius-md) !important; box-shadow: var(--shadow-lg) !important; }
[data-baseweb="menu"] { border-radius: var(--radius-md) !important; background: var(--surface-raised) !important; }
[data-baseweb="option"]:hover { background: rgba(79,110,247,.1) !important; }

/* ── TABS ─────────────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
  gap: .35rem !important;
  background: var(--surface) !important;
  border-radius: var(--radius-lg) !important;
  padding: .35rem !important;
  border: 1px solid var(--border-soft) !important;
}
.stTabs [data-baseweb="tab"] {
  border-radius: var(--radius-md) !important;
  font-weight: 600 !important;
  font-size: .84rem !important;
  color: var(--text-muted) !important;
  transition: var(--transition) !important;
}
.stTabs [aria-selected="true"] {
  background: linear-gradient(135deg,var(--brand-1),var(--brand-2)) !important;
  color: #fff !important;
  box-shadow: var(--shadow-brand) !important;
}

/* ── ALERTS ───────────────────────────────────────────────────────────── */
.stAlert { border-radius: var(--radius-md) !important; border: none !important;
            backdrop-filter: blur(8px) !important; }
div[data-testid="stNotification"] { border-radius: var(--radius-md) !important; }

/* ── TOAST ────────────────────────────────────────────────────────────── */
div[data-testid="stToast"] {
  border-radius: var(--radius-lg) !important;
  backdrop-filter: blur(20px) saturate(200%) !important;
  background: var(--surface-raised) !important;
  border: 1px solid var(--border-soft) !important;
  box-shadow: var(--shadow-lg) !important;
  font-size: .84rem !important;
  font-weight: 500 !important;
  animation: fadeIn .25s ease both !important;
}

/* ── PROGRESS ─────────────────────────────────────────────────────────── */
.stProgress > div > div > div {
  background: linear-gradient(90deg,var(--brand-1),var(--brand-2)) !important;
  border-radius: 4px !important;
}

/* ── PLOTLY CHARTS ────────────────────────────────────────────────────── */
.js-plotly-plot { border-radius: var(--radius-md) !important; }

/* ── DIVIDERS ─────────────────────────────────────────────────────────── */
hr { border: none; border-top: 1px solid var(--border-soft); margin: 1.2rem 0; }

/* ── EDIT BANNER ──────────────────────────────────────────────────────── */
.edit-banner {
  background: linear-gradient(135deg,rgba(245,158,11,.12),rgba(239,68,68,.08));
  border: 1px solid rgba(245,158,11,.3); border-radius: var(--radius-md);
  padding: .9rem 1.2rem; margin-bottom: 1rem; color: var(--text-primary);
}

/* ── DANGER BOX ───────────────────────────────────────────────────────── */
.danger-box {
  border: 1.5px solid rgba(239,68,68,.4); border-radius: var(--radius-md);
  padding: 1rem 1.2rem;
  background: linear-gradient(135deg,rgba(239,68,68,.04),rgba(239,68,68,.02));
}

/* ── SCROLLBAR ────────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 10px; }
::-webkit-scrollbar-thumb:hover { background: var(--brand-1); }

/* ── SPINNER ──────────────────────────────────────────────────────────── */
.stSpinner > div { border-top-color: var(--brand-1) !important; }

/* ── CHECKBOX / RADIO ─────────────────────────────────────────────────── */
.stCheckbox > label, .stRadio > label { font-size: .85rem !important; font-weight: 500 !important; }

/* ── COLUMN CONFIG PANEL ──────────────────────────────────────────────── */
.classifier-box { padding: 1rem; border-radius: var(--radius-lg) !important; }

/* ── REMOVE STREAMLIT BOTTOM GAP ─────────────────────────────────────── */
.block-container { padding-bottom: 0 !important; }

/* ── NAVBAR BUTTON OVERRIDES (keep compact, never wrap) ──────────────── */
/* Target buttons in the very first row of the page (navbar area) */
div[data-testid="stHorizontalBlock"]:first-of-type .stButton > button {
  padding: .3rem .75rem !important;
  font-size: .78rem !important;
  font-weight: 600 !important;
  white-space: nowrap !important;
  min-height: unset !important;
}
</style>
""", unsafe_allow_html=True)


def render_navbar(active_page: str = "home"):
    """Render top navbar with brand + nav links as native Streamlit buttons."""
    token = st.query_params.get("t", "")
    logo_src = logo_data_uri()
    icon_html = (
        f'<img class="brand-logo-img" src="{logo_src}" alt="{BRAND_NAME} logo">'
        if logo_src else '&#128202;'
    )
    home_url = f"?p=home&t={escape(str(token), quote=True)}" if token else "?p=home"

    st.markdown(
        f'<div class="ly-navbar">'
        f'  <a class="ly-navbar-brand" href="{home_url}" target="_self">'
        f'    {icon_html}<span class="brand">{BRAND_NAME}</span>'
        f'  </a>'
        f'</div>',
        unsafe_allow_html=True
    )


def render_logo():
    token    = st.query_params.get("t", "")
    home_url = f"?p=home&t={escape(str(token), quote=True)}" if token else "?p=home"
    logo_src = logo_data_uri()
    icon_html = (
        f'<img class="brand-logo-img" src="{logo_src}" alt="{BRAND_NAME} logo">'
        if logo_src else '<span style="font-size:1.5rem;line-height:1;">&#128202;</span>'
    )
    st.markdown(
        f'<a href="{home_url}" target="_self" '
        f'style="text-decoration:none;display:inline-flex;align-items:center;gap:6px;">'
        f'{icon_html}<span class="brand">{BRAND_NAME}</span></a>',
        unsafe_allow_html=True
    )


def render_page_steps(current: str):
    """Render the Upload → Analysis → Dashboard step indicator."""
    steps = [
        ("upload",   "📁", "Upload"),
        ("analysis", "🔬", "Analyse"),
        ("dashboard","📊", "Dashboard"),
    ]
    order  = [s[0] for s in steps]
    cur_i  = order.index(current) if current in order else 0
    parts  = []
    for i, (sid, icon, label) in enumerate(steps):
        if i < cur_i:
            cls = "done"
            num = "✓"
        elif i == cur_i:
            cls = "active"
            num = str(i + 1)
        else:
            cls = ""
            num = str(i + 1)
        parts.append(
            f'<div class="ly-step {cls}">'
            f'  <span class="step-num">{num}</span>'
            f'  {icon} {label}'
            f'</div>'
        )
        if i < len(steps) - 1:
            parts.append('<span class="ly-step-sep">›</span>')

    st.markdown(
        f'<div class="ly-steps">{"".join(parts)}</div>',
        unsafe_allow_html=True
    )


def inject_footer():
    import streamlit.components.v1 as components
    st.markdown("<div style='margin-top:4rem;'></div>", unsafe_allow_html=True)
    footer_logo = logo_data_uri()
    footer_html = """<!DOCTYPE html><html><head><style>
*{box-sizing:border-box;margin:0;padding:0;}
body{font-family:Inter,system-ui,sans-serif;font-size:14px;}
.ft{padding:28px 20px 18px;border-top:1px solid rgba(128,128,128,.15);}
.ft-grid{display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:28px;margin-bottom:24px;}
@media(prefers-color-scheme:dark){
  .ft-brand{color:#818cf8;}.ft-tagline,.ft-link{color:#94a3b8;}.ft-col-title{color:#64748b;}
  .ft-social-btn{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);color:#94a3b8;}
  .ft-social-btn:hover{border-color:#818cf8;color:#818cf8;}
  .ft-badge{background:rgba(79,110,247,.15);border:1px solid rgba(79,110,247,.3);color:#818cf8;}
  .ft-bottom{color:#64748b;border-color:rgba(255,255,255,.08);}
}
@media(prefers-color-scheme:light){
  .ft-brand{color:#4f6ef7;}.ft-tagline,.ft-link{color:#64748b;}.ft-col-title{color:#94a3b8;}
  .ft-social-btn{background:rgba(0,0,0,.04);border:1px solid rgba(0,0,0,.1);color:#64748b;}
  .ft-social-btn:hover{border-color:#4f6ef7;color:#4f6ef7;}
  .ft-badge{background:rgba(79,110,247,.08);border:1px solid rgba(79,110,247,.2);color:#4f6ef7;}
  .ft-bottom{color:#94a3b8;border-color:rgba(0,0,0,.08);}
}
.ft-brand{font-size:17px;font-weight:800;letter-spacing:-.03em;margin-bottom:7px;display:inline-flex;align-items:center;gap:7px;}
.ft-brand img{width:20px;height:20px;object-fit:contain;}
.ft-tagline{font-size:12px;line-height:1.7;margin-bottom:13px;}
.ft-social{display:flex;gap:7px;flex-wrap:wrap;}
.ft-social-btn{display:inline-flex;align-items:center;gap:5px;padding:4px 11px;border-radius:8px;font-size:12px;font-weight:500;text-decoration:none;transition:border-color .15s,color .15s;}
.ft-col-title{font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;margin-bottom:11px;}
.ft-link{display:block;font-size:12.5px;text-decoration:none;margin-bottom:7px;transition:color .15s;}
.ft-link:hover{color:#4f6ef7!important;}
.ft-bottom{display:flex;justify-content:space-between;align-items:center;padding-top:14px;border-top:1px solid;font-size:11px;flex-wrap:wrap;gap:7px;}
.ft-badge{display:inline-block;padding:2px 8px;border-radius:20px;font-size:10.5px;font-weight:600;margin-left:4px;}
</style></head><body>
<div class="ft">
  <div class="ft-grid">
    <div>
      <div class="ft-brand"><img src="__LOGO__" alt="Lytrize"> Lytrize</div>
      <div class="ft-tagline">Open-source, browser-based data analysis.<br>Upload. Explore. Share. No code required.</div>
      <div class="ft-social">
        <a class="ft-social-btn" href="https://github.com/VidalNat/Lytrize" target="_blank">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/></svg>GitHub</a>
        <a class="ft-social-btn" href="https://www.linkedin.com/in/vishal-nath/" target="_blank">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 0 1-2.063-2.065 2.064 2.064 0 1 1 2.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>LinkedIn</a>
      </div>
    </div>
    <div>
      <div class="ft-col-title">Product</div>
      <a class="ft-link" href="https://github.com/VidalNat/dataLyze/wiki" target="_blank">Features</a>
      <a class="ft-link" href="https://github.com/VidalNat/dataLyze/wiki/Roadmap" target="_blank">Roadmap</a>
      <a class="ft-link" href="https://github.com/VidalNat/dataLyze/discussions/categories/change-logs" target="_blank">Changelog</a>
    </div>
    <div>
      <div class="ft-col-title">Resources</div>
      <a class="ft-link" href="https://github.com/VidalNat/datalyze/wiki" target="_blank">Documentation</a>
      <a class="ft-link" href="https://github.com/VidalNat/dataLyze/wiki/Getting-started" target="_blank">Getting Started</a>
      <a class="ft-link" href="https://github.com/VidalNat/dataLyze/discussions/categories/bug-reports" target="_blank">Report a Bug</a>
    </div>
    <div>
      <div class="ft-col-title">Support</div>
      <a class="ft-link" href="https://github.com/VidalNat/dataLyze/issues/new" target="_blank">Open an Issue</a>
      <a class="ft-link" href="https://github.com/VidalNat/dataLyze/discussions" target="_blank">Discussions</a>
      <a class="ft-link" href="mailto:bantybnath@email.com">Contact Us</a>
    </div>
  </div>
  <div class="ft-bottom">
    <span>© 2026 Lytrize &nbsp;·&nbsp; MIT License</span>
    <span>Built with ❤️ using
      <span class="ft-badge">Streamlit</span>
      <span class="ft-badge">Plotly</span>
      <span class="ft-badge">Python</span>
    </span>
  </div>
</div></body></html>"""
    components.html(
        footer_html.replace("__LOGO__", footer_logo),
        height=248, scrolling=False
    )
