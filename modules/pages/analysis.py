"""
modules/pages/analysis.py
Two-step "Configure → Generate" flow — no st.form.
All config widgets are reactive; options like Top N and Dual Y show/hide instantly.
"""

import uuid, json
import streamlit as st
from modules.database import validate_token, log_activity, save_draft
from modules.analysis import (
    ANALYSIS_OPTIONS, _NEEDS_AXES, _NO_FORM,
    render_config_panel, _collect_kwargs, _run,
)
from modules.analysis.runners   import run_descriptive
from modules.analysis.data_quality import run_data_quality
from modules.analysis.outlier   import OUTLIER_HELP
from modules.charts import charts_to_json, clean_insight_text, generate_chart_insights
from modules.ui.css import inject_footer, render_logo


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
                st.session_state.page = "upload"; st.rerun()
        with c2:
            if st.button("📊 Go to Dashboard →", use_container_width=True):
                _persist_draft("dashboard")
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
        sname = st.session_state.get("editing_session_name", "Session")
        st.info(f"✏️ Edit mode — adding charts to **{sname}**. "
                f"Click **Proceed to Dashboard** when done.")

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
                st.rerun()

    # ── Active analysis config panel ──────────────────────────────────────────
    if active:
        analysis_name = next(o["name"] for o in ANALYSIS_OPTIONS if o["id"] == active)
        st.markdown("---")
        # Auto-scroll to Configure section for better UX
        import streamlit.components.v1 as _comp
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

        # ── Data Quality — special case (no config needed) ────────────────────
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
                    st.rerun()
            with c2:
                if st.button("✕ Close", key="dq_close"):
                    st.session_state["_active_analysis"] = None; st.rerun()

        # ── Descriptive — no chart output ─────────────────────────────────────
        elif active == "descriptive":
            st.markdown("### 🗂️ Descriptive Statistics")
            run_descriptive(df)
            c1, c2, _ = st.columns([1, 1, 5])
            with c1:
                if st.button("✅ Keep in Analysis", key="desc_add"):
                    if active not in st.session_state.selected_analyses:
                        st.session_state.selected_analyses.append(active)
                    log_activity(st.session_state.get("user_id",0),"analysis_run","type=descriptive")
                    st.session_state["_active_analysis"] = None; st.rerun()
            with c2:
                if st.button("✕ Close", key="desc_close"):
                    st.session_state["_active_analysis"] = None; st.rerun()

        # ── All other analysis types — two-step: configure then generate ──────
        else:
            st.markdown(f"### ⚙️ Configure — {analysis_name}")
            st.caption("Adjust options below. All selections are live — no submit needed until Generate.")

            # Render config widgets (fully reactive — no form)
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
                st.session_state["_active_analysis"] = None; st.rerun()

            if generate_clicked:
                kwargs = _collect_kwargs(active, df)
                new_charts = _run(active, df, **kwargs)
                if new_charts is not None:
                    if new_charts:
                        _add_charts(new_charts, active)
                    st.session_state["_active_analysis"] = None
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
                _persist_draft()
                st.rerun()

        _render_chart_list(st.session_state.charts, edit_mode=False)

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🎯 Proceed to Dashboard →", type="primary"):
            log_activity(st.session_state.get("user_id",0),"proceed_to_dashboard",
                         f"charts={len(st.session_state.charts)}")
            _persist_draft("dashboard")
            st.session_state.page = "dashboard"; st.rerun()

    inject_footer()


def _render_chart_list(charts, edit_mode=False):
    """Render chart cards with delete, insights, and notes. Title editing is in Dashboard → Chart Settings."""
    col_descs = st.session_state.get("col_descriptions", {})
    for uid, title, fig in charts:
        # ── Compact control row (delete only — title lives inside the Plotly chart) ──
        ctrl = st.columns([11, 1])
        with ctrl[1]:
            if st.button("✕", key=f"del_{uid}", help="Remove this chart"):
                log_activity(st.session_state.get("user_id",0),"chart_deleted",f"title='{title}'")
                st.session_state.charts = [c for c in st.session_state.charts if c[0] != uid]
                _persist_draft()
                st.rerun()

        # Apply axis readability before rendering
        import copy as _acopy
        fig_show = _acopy.deepcopy(fig)
        is_horiz = any(getattr(t, "orientation", "v") == "h"
                       for t in fig_show.data if hasattr(t, "orientation"))
        if is_horiz:
            fig_show.update_yaxes(tickfont=dict(size=10), automargin=True)
            fig_show.update_xaxes(tickfont=dict(size=10))
            fig_show.update_layout(margin=dict(l=120, r=20, t=48, b=20))
        else:
            fig_show.update_xaxes(tickangle=-35, tickfont=dict(size=10), automargin=True)
            fig_show.update_yaxes(tickfont=dict(size=10), automargin=True)
            fig_show.update_layout(margin=dict(l=20, r=20, t=48, b=80))
        st.plotly_chart(fig_show, use_container_width=True)

        # ── Insights ──────────────────────────────────────────────────────────
        chart_type    = st.session_state.get(f"chart_type_{uid}", "")
        auto_insights = st.session_state.get(f"auto_insights_{uid}")
        if auto_insights is None:
            auto_insights = generate_chart_insights(chart_type, title, fig, col_descs)
            st.session_state[f"auto_insights_{uid}"] = auto_insights

        if auto_insights:
            with st.expander("💡 Insights", expanded=not edit_mode):
                for ins in auto_insights:
                    st.markdown(f"- {clean_insight_text(ins)}")

        # ── Analysis Notes ────────────────────────────────────────────────────
        st.text_area(
            "✍️ Analysis Notes (saved to Dashboard)",
            value=st.session_state.get(f"desc_{uid}", ""),
            key=f"desc_{uid}",
            placeholder="Add your findings or observations here…")
