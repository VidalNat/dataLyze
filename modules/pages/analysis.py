"""
modules/pages/analysis.py -- Analysis selection and chart generation page.
==========================================================================

Orchestrates the user flow between selecting analyses, configuring them,
generating charts, and navigating to the dashboard.

Flow on each rerun:
    1. Render the analysis card grid (ANALYSIS_OPTIONS from __init__.py).
    2. When the user clicks a card, it is added to selected_analyses.
    3. For each selected analysis, render its config panel via render_config_panel().
    4. "Generate Charts" button calls _run() for each selected analysis and
       appends results to st.session_state.charts.
    5. "Go to Dashboard" button navigates to the dashboard page.

Special handling:
    - data_quality bypasses the st.form() wrapper (listed in _NO_FORM) because
      it contains its own st.button() widgets.
    - descriptive renders inline via st.dataframe() and returns no charts.
    - OUTLIER_HELP text is displayed above outlier charts.
    - Auto-insights are generated via generate_chart_insights() after each chart.

CONTRIBUTING -- after adding a new analysis type in __init__.py:
    No changes needed here unless your analysis requires special page-level
    handling (like data_quality does). The card grid, config panel, and chart
    generation all read from ANALYSIS_OPTIONS and _RUNNERS automatically.
"""
"""
modules/pages/analysis.py
Two-step "Configure → Generate" flow -- no st.form.
All config widgets are reactive; options like Top N and Dual Y show/hide instantly.
"""

import uuid, json
import streamlit as st
import streamlit.components.v1 as _comp
from modules.database import validate_token, log_activity, save_draft, update_session_db, get_session_meta
from modules.analysis import (
    ANALYSIS_OPTIONS, _NEEDS_AXES, _NO_FORM,
    render_config_panel, _collect_kwargs, _run,
    render_config_panel_scoped, _collect_kwargs_scoped,
)
from modules.analysis.runners   import run_descriptive
from modules.analysis.data_quality import run_data_quality
from modules.analysis.outlier   import OUTLIER_HELP
from modules.charts import charts_to_json, clean_insight_text, generate_chart_insights
from modules.ui.css import inject_footer, render_logo


def _shadow_notes_sync() -> None:
    """
    Copy all live desc_{uid} widget values into st.session_state._notes_shadow.

    _notes_shadow is a plain dict (not widget-keyed) so it survives st.rerun()
    regardless of whether the text_area widgets are rendered in the current run.

    Call this BEFORE any st.rerun() in an action handler that fires before
    _render_chart_list is reached — which is every handler in the config panel,
    the regen panel, and the buttons at the top of each chart card.
    """
    shadow = st.session_state.setdefault("_notes_shadow", {})
    for k, v in list(st.session_state.items()):
        if k.startswith("desc_") and k not in ("desc_add", "desc_close"):
            shadow[k[5:]] = v   # strip "desc_" prefix → uid


def _sync_one_note(uid: str) -> None:
    """on_change callback for a single notes text_area.  Writes the new value
    into the shadow dict immediately so it is never lost to a subsequent rerun."""
    val = st.session_state.get(f"desc_{uid}", "")
    st.session_state.setdefault("_notes_shadow", {})[uid] = val


def _autosave() -> None:
    """
    Persist the current chart/notes state to the database on every meaningful
    user action (chart add, delete, regen, settings save).

    Two-level write:
      1. draft_sessions — always written; survives browser refresh.
      2. sessions table — written when editing_session_id is set, so the saved
         session is updated in-place and notes are never lost even if the user
         closes the tab without reaching the dashboard Save button.

    KPI preservation: the analysis page never loads or manages KPIs, so
    st.session_state.kpis is absent here.  We read the current kpis_json from
    the DB rather than overwriting it with "[]", which would silently wipe
    any KPIs the user added on the dashboard.
    """
    _shadow_notes_sync()
    _persist_draft()
    eid  = st.session_state.get("editing_session_id")
    uid  = st.session_state.get("user_id")
    name = st.session_state.get("editing_session_name", "Session")
    if eid and uid:
        try:
            # Preserve KPIs: analysis page never sets st.session_state.kpis, so
            # if it's absent we must read the saved value rather than write "[]".
            if "kpis" in st.session_state:
                kpis_json = json.dumps(st.session_state["kpis"])
            else:
                try:
                    sm = get_session_meta(eid, uid)
                    kpis_json = sm.get("kpis_json", "[]") if sm else "[]"
                except Exception:
                    kpis_json = "[]"

            update_session_db(
                eid, name,
                charts_to_json(st.session_state.get("charts", [])),
                st.session_state.get("selected_analyses", []),
                uid,
                dashboard_title = st.session_state.get("dashboard_title", ""),
                kpis_json       = kpis_json,
                layout_mode     = st.session_state.get("layout_mode", "portrait"),
            )
            try:
                st.toast("✅ Auto-saved", icon="✅")
            except Exception:
                pass  # toast unavailable in older Streamlit builds
        except Exception:
            pass  # DB errors must never block the UI


def _restore_edit_notes() -> None:
    """
    Re-seed desc_{uid} keys for all charts in the current editing session.

    Checks _notes_shadow first (catches notes typed after the last DB save),
    then falls back to the sessions table for the initial load.

    Guard: skipped when _analysis_notes_loaded is already True so the DB is
    hit at most once per edit session.  The flag is cleared by home.py on Edit
    click, and by _autosave/_do_update after every save.
    """
    if st.session_state.get("_analysis_notes_loaded"):
        # Shadow dict is always kept current, so re-seed from it on every entry.
        # This handles the case where the user typed a note, a rerun wiped the
        # widget key, and they land back on the page — shadow still has the value.
        shadow = st.session_state.get("_notes_shadow", {})
        for uid, note in shadow.items():
            key = f"desc_{uid}"
            if note and not st.session_state.get(key):
                st.session_state[key] = note
        return

    eid = st.session_state.get("editing_session_id")
    uid = st.session_state.get("user_id")
    if not eid or not uid:
        st.session_state["_analysis_notes_loaded"] = True
        return
    from modules.database import get_session_charts
    try:
        saved = get_session_charts(eid, uid)
        for chart_uid, _title, _fig, desc, _auto, _ctype, _meta in saved:
            note_key = f"desc_{chart_uid}"
            # Prefer shadow (contains notes typed since last DB save).
            shadow_val = st.session_state.get("_notes_shadow", {}).get(chart_uid, "")
            restore_val = shadow_val or desc
            if restore_val and not st.session_state.get(note_key):
                st.session_state[note_key] = restore_val
                st.session_state.setdefault("_notes_shadow", {})[chart_uid] = restore_val
    except Exception:
        pass  # DB errors must never break the analysis page.
    st.session_state["_analysis_notes_loaded"] = True


def _persist_draft(page="analysis"):
    uid = st.session_state.get("user_id")
    if not uid:
        return
    save_draft(
        user_id              = uid,
        page                 = page,
        charts_json          = charts_to_json(st.session_state.get("charts", [])),
        file_name            = st.session_state.get("file_name", ""),
        editing_session_id   = st.session_state.get("editing_session_id"),
        editing_session_name = st.session_state.get("editing_session_name"),
        dashboard_title      = st.session_state.get("dashboard_title", ""),
        kpis_json            = json.dumps(st.session_state.get("kpis", [])),
        chart_meta_json      = json.dumps({
            k: v for k, v in st.session_state.items()
            if k.startswith("chart_meta_")
        }),
        layout_mode          = st.session_state.get("layout_mode", "portrait"),
    )


def _add_charts(new_charts, active):
    col_descs = st.session_state.get("col_descriptions", {})
    for uid, title, fig in new_charts:
        st.session_state[f"chart_type_{uid}"]    = active
        st.session_state[f"auto_insights_{uid}"] = generate_chart_insights(
            active, title, fig, col_descs)
    st.session_state.charts.extend(new_charts)
    st.session_state._last_analysis_type = active
    if active not in st.session_state.selected_analyses:
        st.session_state.selected_analyses.append(active)
    log_activity(st.session_state.get("user_id", 0), "analysis_run",
                 f"type={active} charts_added={len(new_charts)}")
    _persist_draft()


def page_analysis():
    token = st.query_params.get("t", "")
    if token and "user_id" not in st.session_state:
        restored = validate_token(token)
        if restored:
            st.session_state.user_id  = restored[0]
            st.session_state.username = restored[1]
            st.session_state.page     = "analysis"
            st.rerun()

    df         = st.session_state.get("df")
    is_editing = "editing_session_id" in st.session_state

    render_logo()

    # ── Edit mode without df ──────────────────────────────────────────────────
    if df is None and is_editing:
        _restore_edit_notes()   # Re-seed notes cleared by Streamlit widget cleanup
        sname  = st.session_state.get("editing_session_name", "Session")
        fname  = st.session_state.get("editing_file_name",    "the original file")
        charts = st.session_state.get("charts", [])

        if st.button("← Home"):
            for k in ["editing_session_id","editing_session_name","editing_file_name"]:
                st.session_state.pop(k, None)
            st.session_state.page = "home"; st.rerun()

        st.markdown(f"## ✏️ Editing: **{sname}**")
        st.info(
            f"📂 **Re-upload needed to run new analyses.** "
            f"Upload **{fname}** to add more charts, or go to Dashboard to save what you have.")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("📂 Upload Dataset to Add Charts", use_container_width=True):
                # Sync shadow + autosave to DB before leaving so notes are safe
                # even while the upload page is rendered (Streamlit wipes desc_ keys then).
                _autosave()
                # Clear the notes-loaded flag so _restore_edit_notes() re-seeds
                # desc_{uid} keys from shadow + DB when we return.
                st.session_state.pop("_analysis_notes_loaded", None)
                st.session_state.page = "upload"; st.rerun()
        with c2:
            if st.button("📊 Go to Dashboard →", use_container_width=True):
                _autosave()
                st.session_state.page = "dashboard"; st.rerun()

        _render_chart_list(charts, edit_mode=True)
        inject_footer()
        return

    if df is None:
        st.session_state.page = "upload"; st.rerun()

    if "charts"            not in st.session_state: st.session_state.charts            = []
    if "selected_analyses" not in st.session_state: st.session_state.selected_analyses = []

    if st.button("← Home"):
        st.session_state.page = "home"; st.rerun()

    if is_editing:
        _restore_edit_notes()   # Re-seed notes that Streamlit cleared during upload navigation
        sname = st.session_state.get("editing_session_name", "Session")
        st.info(f"✏️ Edit mode -- adding charts to **{sname}**. "
                f"Click **Proceed to Dashboard** when done.")

    # ── Chart Regeneration Panel ─────────────────────────────────────────────
    # Triggered when user clicks "🔄 Edit Chart" on an existing chart.
    # Shows the full config panel for that chart's analysis type, scoped to
    # its uid so widget keys never collide with the main analysis panel.
    regen_uid  = st.session_state.get("_regen_uid")
    regen_type = st.session_state.get("_regen_type", "")
    if regen_uid and regen_type and df is not None:
        chart_entry = next(
            (c for c in st.session_state.get("charts", []) if c[0] == regen_uid), None)
        if chart_entry:
            regen_title = chart_entry[1]
            type_label  = next(
                (o["name"] for o in ANALYSIS_OPTIONS if o["id"] == regen_type),
                regen_type)
            st.markdown(f"### 🔄 Regenerate Chart — *{regen_title}* ({type_label})")
            st.caption("Adjust options below then click **Apply Changes** to replace the chart.")

            render_config_panel_scoped(regen_uid, regen_type, df)

            ra, rb, _ = st.columns([1, 1, 5])
            with ra:
                if st.button("✅ Apply Changes", key="regen_apply", type="primary",
                             use_container_width=True):
                    kwargs = _collect_kwargs_scoped(regen_uid, regen_type, df)
                    new_charts = _run(regen_type, df, **kwargs)
                    if new_charts:
                        # Replace the existing chart in-place (keep uid + position)
                        new_fig   = new_charts[0][2]  # take first generated chart
                        new_title = new_charts[0][1]
                        st.session_state.charts = [
                            (c[0], new_title if c[0] == regen_uid else c[1],
                             new_fig  if c[0] == regen_uid else c[2])
                            for c in st.session_state.get("charts", [])
                        ]
                        # Refresh auto-insights for the replaced chart
                        st.session_state.pop(f"auto_insights_{regen_uid}", None)
                        st.session_state[f"chart_type_{regen_uid}"] = regen_type
                    st.session_state.pop("_regen_uid",  None)
                    st.session_state.pop("_regen_type", None)
                    _autosave()
                    st.rerun()
            with rb:
                if st.button("✕ Cancel", key="regen_cancel", use_container_width=True):
                    st.session_state.pop("_regen_uid",  None)
                    st.session_state.pop("_regen_type", None)
                    _shadow_notes_sync()
                    st.rerun()

            st.markdown("---")

    st.markdown("## 🔬 Select Analysis Type")

    active = st.session_state.get("_active_analysis")
    cols   = st.columns(4)
    for i, opt in enumerate(ANALYSIS_OPTIONS):
        with cols[i % 4]:
            selected = opt["id"] == active
            st.markdown(
                f'<div class="ag-card" style="{"border-color:#4f6ef7;box-shadow:0 0 0 3px rgba(79,110,247,0.18);" if selected else ""}">'
                f'<div class="ag-icon">{opt["icon"]}</div>'
                f'<div class="ag-name">{opt["name"]}</div>'
                f'<div class="ag-desc">{opt["desc"]}</div></div>',
                unsafe_allow_html=True)
            if st.button("▶ Select", key=f"btn_{opt['id']}"):
                if st.session_state.get("_active_analysis") == opt["id"]:
                    st.session_state["_active_analysis"] = None
                else:
                    st.session_state["_active_analysis"] = opt["id"]
                _shadow_notes_sync()
                st.rerun()

    # ── Active analysis config panel ──────────────────────────────────────────
    if active:
        analysis_name = next(o["name"] for o in ANALYSIS_OPTIONS if o["id"] == active)
        st.markdown("---")
        # Auto-scroll to Configure section for better UX
        _comp.html("""<script>
        setTimeout(function(){
            var els = window.parent.document.querySelectorAll('h3');
            for(var el of els){
                if(el.textContent && el.textContent.includes('Configure')){
                    el.scrollIntoView({behavior:'smooth',block:'start'});
                    break;
                }
            }
        }, 150);
        </script>""", height=0)

        # ── Data Quality -- special case (no config needed) ────────────────────
        if active in _NO_FORM:
            st.markdown(f"### 🧹 {analysis_name}")
            new_charts_raw = run_data_quality(df)
            new_charts = [(str(uuid.uuid4())[:8], t, f) for t, f in new_charts_raw]

            c1, c2, _ = st.columns([1, 1, 5])
            with c1:
                if st.button("✅ Add to Analysis", key="dq_add"):
                    if new_charts:
                        _add_charts(new_charts, active)
                    st.session_state["_active_analysis"] = None
                    _autosave()
                    st.rerun()
            with c2:
                if st.button("✕ Close", key="dq_close"):
                    st.session_state["_active_analysis"] = None
                    _shadow_notes_sync()
                    st.rerun()

        # ── Descriptive -- no chart output ─────────────────────────────────────
        elif active == "descriptive":
            st.markdown("### 🗂️ Descriptive Statistics")
            run_descriptive(df)
            c1, c2, _ = st.columns([1, 1, 5])
            with c1:
                if st.button("✅ Keep in Analysis", key="desc_add"):
                    if active not in st.session_state.selected_analyses:
                        st.session_state.selected_analyses.append(active)
                    log_activity(st.session_state.get("user_id",0),"analysis_run","type=descriptive")
                    st.session_state["_active_analysis"] = None
                    _shadow_notes_sync()
                    st.rerun()
            with c2:
                if st.button("✕ Close", key="desc_close"):
                    st.session_state["_active_analysis"] = None
                    _shadow_notes_sync()
                    st.rerun()

        # ── All other analysis types -- two-step: configure then generate ──────
        else:
            st.markdown(f"### ⚙️ Configure -- {analysis_name}")
            st.caption("Adjust options below. All selections are live -- no submit needed until Generate.")

            # Render config widgets (fully reactive -- no form)
            render_config_panel(active, df)

            st.markdown("<br>", unsafe_allow_html=True)
            g1, g2, _ = st.columns([1, 1, 5])
            with g1:
                generate_clicked = st.button(
                    "▶ Generate Charts", key=f"gen_{active}",
                    type="primary", use_container_width=True)
            with g2:
                close_clicked = st.button(
                    "✕ Close", key=f"close_{active}",
                    use_container_width=True)

            if close_clicked:
                st.session_state["_active_analysis"] = None
                _shadow_notes_sync()
                st.rerun()

            if generate_clicked:
                kwargs = _collect_kwargs(active, df)
                new_charts = _run(active, df, **kwargs)
                if new_charts is not None:
                    if new_charts:
                        _add_charts(new_charts, active)
                    st.session_state["_active_analysis"] = None
                    _autosave()
                    st.rerun()

    # ── Generated charts ──────────────────────────────────────────────────────
    if st.session_state.charts:
        st.markdown("---")
        h1, h2 = st.columns([5, 1])
        with h1:
            st.markdown(f"## 📈 Generated Charts ({len(st.session_state.charts)})")
        with h2:
            if st.button("🗑️ Clear All", key="clear_all_charts"):
                log_activity(st.session_state.get("user_id",0),"charts_cleared_all",
                             f"count={len(st.session_state.charts)}")
                st.session_state.charts = []
                st.session_state.selected_analyses = []
                st.session_state.pop("_notes_shadow", None)   # charts gone, clear shadow too
                _autosave()
                st.rerun()

        _render_chart_list(st.session_state.charts, edit_mode=is_editing)

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🎯 Proceed to Dashboard →", type="primary"):
            log_activity(st.session_state.get("user_id",0),"proceed_to_dashboard",
                         f"charts={len(st.session_state.charts)}")
            _autosave()
            st.session_state.page = "dashboard"; st.rerun()

    inject_footer()


def _chart_meta(uid) -> dict:
    """Read chart meta from session_state (same structure as dashboard._meta)."""
    k = f"chart_meta_{uid}"
    if k not in st.session_state:
        st.session_state[k] = {}
    return st.session_state[k]


def _set_chart_meta(uid, **kw) -> None:
    """Write chart meta to session_state."""
    k = f"chart_meta_{uid}"
    if k not in st.session_state:
        st.session_state[k] = {}
    st.session_state[k].update(kw)


def _render_chart_list(charts, edit_mode=False):
    """Render chart cards with full settings, insights, and notes in edit mode."""
    col_descs = st.session_state.get("col_descriptions", {})
    for uid, title, fig in charts:
        meta = _chart_meta(uid)

        # ── Header row: display title + action buttons ────────────────────────
        display_title = meta.get("custom_title") or title
        df_available  = st.session_state.get("df") is not None
        ctrl = st.columns([9, 2, 1])
        with ctrl[0]:
            st.markdown(
                f'''<div style="font-size:1rem;font-weight:700;color:#1e293b;
                margin-bottom:0.2rem;">{display_title}</div>''',
                unsafe_allow_html=True)
            if meta.get("subtitle"):
                st.caption(meta["subtitle"])
        with ctrl[1]:
            chart_type = st.session_state.get(f"chart_type_{uid}", "")
            if chart_type and chart_type not in ("descriptive", "data_quality"):
                if df_available:
                    if st.button("🔄 Edit Chart", key=f"regen_btn_{uid}",
                                 use_container_width=True,
                                 help="Re-run this chart with new columns / settings"):
                        st.session_state._regen_uid  = uid
                        st.session_state._regen_type = chart_type
                        # Clear old scoped widget keys so panel starts fresh
                        for k in list(st.session_state.keys()):
                            if k.startswith(f"_edit_{uid}_"):
                                del st.session_state[k]
                        _shadow_notes_sync()   # protect notes before rerun skips text_areas
                        st.rerun()
                else:
                    st.button("🔄 Edit Chart", key=f"regen_btn_{uid}",
                              use_container_width=True, disabled=True,
                              help="Upload the original dataset first to regenerate this chart")
        with ctrl[2]:
            if st.button("✕", key=f"del_{uid}", help="Remove this chart"):
                log_activity(st.session_state.get("user_id",0),"chart_deleted",f"title='{title}'")
                st.session_state.charts = [c for c in st.session_state.charts if c[0] != uid]
                st.session_state.pop("_regen_uid", None)
                st.session_state.get("_notes_shadow", {}).pop(uid, None)  # clean up shadow entry
                _autosave()
                st.rerun()

        # ── Chart plot ────────────────────────────────────────────────────────
        import copy as _acopy
        fig_show = _acopy.deepcopy(fig)
        xl = meta.get("x_label", "")
        yl = meta.get("y_label", "")
        if xl: fig_show.update_xaxes(title_text=xl)
        if yl: fig_show.update_yaxes(title_text=yl)
        fig_show.update_layout(title_text="")
        is_horiz = any(getattr(t, "orientation", "v") == "h"
                       for t in fig_show.data if hasattr(t, "orientation"))
        if is_horiz:
            fig_show.update_yaxes(tickfont=dict(size=10), automargin=True)
            fig_show.update_xaxes(tickfont=dict(size=10))
            fig_show.update_layout(margin=dict(l=120, r=20, t=28, b=20))
        else:
            fig_show.update_xaxes(tickangle=-35, tickfont=dict(size=10), automargin=True)
            fig_show.update_yaxes(tickfont=dict(size=10), automargin=True)
            fig_show.update_layout(margin=dict(l=20, r=20, t=28, b=80))
        st.plotly_chart(fig_show, use_container_width=True)

        # ── Chart Settings expander ───────────────────────────────────────────
        with st.expander("⚙️ Chart Settings", expanded=False):
            new_title = st.text_input(
                "Chart Title",
                value=meta.get("custom_title", "") or title,
                key=f"act_{uid}")
            ca, cb = st.columns(2)
            with ca:
                new_sub = st.text_input(
                    "Subtitle",
                    value=meta.get("subtitle", ""),
                    placeholder="Optional…",
                    key=f"asub_{uid}")
            with cb:
                pass
            cc, cd = st.columns(2)
            with cc:
                new_xl = st.text_input("X-Axis Label",
                                       value=meta.get("x_label", ""),
                                       key=f"axl_{uid}")
            with cd:
                new_yl = st.text_input("Y-Axis Label",
                                       value=meta.get("y_label", ""),
                                       key=f"ayl_{uid}")

            # Auto-insights toggle
            chart_type    = st.session_state.get(f"chart_type_{uid}", "")
            auto_insights = st.session_state.get(f"auto_insights_{uid}")
            if auto_insights is None:
                auto_insights = generate_chart_insights(chart_type, title, fig, col_descs)
                st.session_state[f"auto_insights_{uid}"] = auto_insights

            show_ai  = st.checkbox("Show auto-insights in export",
                                   value=meta.get("show_auto_insights", True),
                                   key=f"asai_{uid}")
            hidden   = set(meta.get("hidden_insights", []))
            new_hidden = set()
            if auto_insights and show_ai:
                st.markdown("**Toggle insights:**")
                for i, ins in enumerate(auto_insights):
                    label = clean_insight_text(ins)
                    if not st.checkbox(
                            label[:80] + ("…" if len(label) > 80 else ""),
                            value=i not in hidden,
                            key=f"ains_{uid}_{i}"):
                        new_hidden.add(i)

            if st.button("💾 Save Settings", key=f"asave_{uid}", type="primary"):
                _set_chart_meta(uid,
                                custom_title=new_title,
                                subtitle=new_sub,
                                x_label=new_xl,
                                y_label=new_yl,
                                show_auto_insights=show_ai,
                                hidden_insights=list(new_hidden))
                # Keep title in charts list in sync
                st.session_state.charts = [
                    (c[0], new_title if c[0] == uid else c[1], c[2])
                    for c in st.session_state.get("charts", [])
                ]
                _autosave()
                st.success("Settings saved!")
                st.rerun()

        # ── Insights (read view below chart) ──────────────────────────────────
        if auto_insights:
            with st.expander("💡 Auto-Insights", expanded=False):
                for ins in auto_insights:
                    st.markdown(f"- {clean_insight_text(ins)}")

        # ── Analysis Notes ────────────────────────────────────────────────────
        # Seed from shadow first (survives any rerun), then empty.
        # Shadow is populated by on_change below and by _autosave()/_restore_edit_notes().
        if f"desc_{uid}" not in st.session_state:
            st.session_state[f"desc_{uid}"] = (
                st.session_state.get("_notes_shadow", {}).get(uid, ""))
        st.text_area(
            "✍️ Analysis Notes (auto-saved to Dashboard)",
            key=f"desc_{uid}",
            on_change=_sync_one_note,
            args=(uid,),
            placeholder="Add your findings or observations here…")

        st.markdown("---")
