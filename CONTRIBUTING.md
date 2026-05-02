# Contributing to Lytrize

Welcome! This guide explains how the codebase is structured and how to
add new features without breaking existing ones.

---

## Project structure

```
lytrize/
├── app.py                        ← Entry point. Run: streamlit run app.py
├── requirements.txt
├── assets/
│   └── lytrize.ico
├── modules/
│   ├── charts.py                 ← Palettes, layout defaults, auto-insight engine
│   ├── database.py               ← All DB operations (SQLite / Postgres)
│   ├── export.py                 ← PDF export engine (fpdf2 + kaleido)
│   ├── analysis/
│   │   ├── __init__.py           ← Analysis registry, config UI, runner dispatcher ★
│   │   ├── categorical.py        ← Bar / column charts
│   │   ├── correlation.py        ← Pearson heatmap
│   │   ├── data_quality.py       ← Missing values & duplicates
│   │   ├── descriptive.py        ← Stats table (no chart output)
│   │   ├── distribution.py       ← Histograms + box plot marginals
│   │   ├── outlier.py            ← IQR-based outlier scatter plots
│   │   ├── pie_chart.py          ← Donut / pie charts
│   │   ├── runners.py            ← Legacy shim — re-exports all runners
│   │   ├── statistical.py        ← Aggregation bar charts
│   │   └── time_series.py        ← Line charts over time
│   ├── pages/
│   │   ├── analysis.py           ← Analysis selection + chart generation page
│   │   ├── auth.py               ← Login, register, profile page
│   │   ├── dashboard.py          ← Dashboard view / edit / save / PDF export page
│   │   ├── home.py               ← Home page with saved sessions grid
│   │   └── upload.py             ← File upload + column classification page
│   └── ui/
│       ├── column_manager.py     ← Dashboard grid layout helpers
│       ├── column_tools.py       ← Column classifier + data transform tools
│       ├── css.py                ← Global CSS injection + logo + footer
│       └── excel_loader.py       ← Excel multi-sheet browser + unified table
```

`★` = the file you edit most often when adding new features.

---

## How to add a new analysis type

This is the most common contribution. It takes 5 steps and touches 2 files.

### Step 1 — Create the runner file

Create `modules/analysis/my_analysis.py`:

```python
"""
modules/analysis/my_analysis.py — One-line description.
"""

def run_my_analysis(df, x_cols=None, palette=None, **kwargs):
    """
    Args:
        df:      Working DataFrame.
        x_cols:  Columns to analyse.
        palette: List of hex colour strings.
        **kwargs: Extra kwargs — always accept and ignore these.

    Returns:
        list of (title: str, fig: plotly.graph_objects.Figure) tuples.
        Return [] if the analysis cannot run (e.g. no suitable columns).
    """
    charts = []
    # ... your chart code here ...
    charts.append(("My Chart Title", fig))
    return charts
```

Rules:
- Always accept `**kwargs` and silently ignore unknown keys.
- Return a list of `(title, fig)` tuples — never render to Streamlit directly.
- Return `[]` rather than raising exceptions when data is insufficient.

### Step 2 — Register in ANALYSIS_OPTIONS

In `modules/analysis/__init__.py`, append to `ANALYSIS_OPTIONS`:

```python
{"id": "my_analysis", "icon": "🧩", "name": "My Analysis", "desc": "Short description"}
```

### Step 3 — Register in _RUNNERS

In the same file, add to `_RUNNERS`:

```python
"my_analysis": run_my_analysis,
```

And add the import at the top:

```python
from modules.analysis.my_analysis import run_my_analysis
```

### Step 4 — Add configuration widgets

In `render_config_panel()` in `__init__.py`:

```python
elif aid == "my_analysis":
    st.multiselect("Columns", num, key=_sk(aid, "cols"))
```

Use `_sk(aid, "key_name")` for every widget key — this prevents conflicts
with other analyses that use the same widget names.

**Important:** Never use conditional widget visibility based on other widget
values within the same rerun. Show all widgets unconditionally. This prevents
Streamlit's "widget key missing" error.

### Step 5 — Collect kwargs

In `_collect_kwargs()` in `__init__.py`:

```python
elif aid == "my_analysis":
    cols = _g(aid, "cols", []) or num
    kwargs.update(cols=cols)
```

`_g(aid, key, default)` reads session_state safely with a fallback.

That's it. The card grid, form rendering, and chart generation all happen automatically.

---

## How to add a new page

1. Create `modules/pages/my_page.py` with a `page_my_page()` function.
2. Import it in `app.py`.
3. Add `elif p == "my_page": page_my_page()` in the router block in `app.py`.
4. Navigate to it from anywhere with:
   ```python
   st.session_state.page = "my_page"
   st.rerun()
   ```

---

## How to add a new colour palette

In `modules/charts.py`, append to `PALETTES`:

```python
"🎨 My Palette": ["#hex1", "#hex2", "#hex3", "#hex4",
                   "#hex5", "#hex6", "#hex7", "#hex8"],
```

The palette selector on the analysis page reads `PALETTES` dynamically —
no other changes needed.

---

## How to add auto-insights for a new analysis type

In `modules/charts.py`, add an `elif` branch in `generate_chart_insights()`:

```python
elif chart_type == "my_analysis" or "my keyword" in tl:
    try:
        data = fig.data[0]
        vals = _as_number_series(data.y)
        insights.append(f"The highest value is {_fmt_num(vals.max())}.")
    except Exception:
        pass
```

Use the helper functions already in `charts.py`:
- `_fmt_num(v)` → "1.2M", "98.8K", "42"
- `_fmt_pct(v)` → "+12.3%"
- `_plural(n, "item")` → "item" or "items"
- `_as_number_series(values)` → numeric pd.Series, NaN dropped
- `_as_list(values)` → safe list conversion

---

## Database — adding a new table or column

1. Add `CREATE TABLE IF NOT EXISTS` blocks in `init_db()` in `database.py`
   for **both** the `_PG` (Postgres) and SQLite branches.
2. Keep both schemas in sync — every column that exists in one must exist in the other.
3. For existing SQLite databases, add an ALTER TABLE migration at the bottom
   of the SQLite branch (errors are silently ignored — column already exists).
4. Add CRUD functions below the schema block with clear docstrings.
5. Import new functions in the page(s) that need them.

**Never call `st.*` inside `database.py`** — it is a pure data layer with no
UI dependencies.

---

## Database backends

| Setting | Value |
|---|---|
| Default | SQLite → `lytrize.db` (or `$DATALYZE_DB_PATH`) |
| Postgres | Set `DATABASE_URL=postgresql://user:pass@host/dbname` |

Switch backends by setting the `DATABASE_URL` environment variable.
The `_ph()`, `_connect()`, and `_last_id()` helpers in `database.py`
abstract away all backend differences.

---

## Style conventions

- **No `st.*` calls in `database.py` or analysis runner files.** These are pure
  data/computation layers. Only page files and `ui/` files touch Streamlit.
- **Accept `**kwargs` in every runner** and silently ignore unknown keys. This
  makes runners forward-compatible when new config options are added.
- **Escape all user content** before embedding in HTML strings. Use
  `html.escape()` from the standard library (already imported in page files).
- **Use `_sk(aid, key)`** for every analysis config widget key to namespace it
  by analysis ID and prevent collisions.
- **Return `[]` rather than raising** from runners when data is insufficient.
  The caller shows a warning; it doesn't crash.

---

## Running locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

For Postgres instead of SQLite:
```bash
export DATABASE_URL=postgresql://user:pass@localhost/lytrize
streamlit run app.py
```
