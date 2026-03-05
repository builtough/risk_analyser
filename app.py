"""
DealAnalyzer — Contract Intelligence Platform
Run: streamlit run app.py
"""
import streamlit as st

st.set_page_config(
    page_title="DealAnalyzer | Contract Intelligence",
    page_icon="⚖️", layout="wide", initial_sidebar_state="expanded",
)

from modules.ui.styles        import inject_styles
from modules.ui.helpers       import doc_pills
from modules.ui.admin         import init_admin_state, render_admin_panel, get_visible_tabs
from modules.ui.sidebar       import render_sidebar
from modules.ui.tab_analysis  import render_tab_analysis
from modules.ui.tab_search    import render_tab_search
from modules.ui.tab_query     import render_tab_query
from modules.ui.tab_viewer    import render_tab_viewer
from modules.ui.tab_dashboard import render_tab_dashboard
from modules.ui.tab_reports   import render_tab_reports
from modules.ui.tab_debug     import render_tab_debug
from modules.ui.tab_tables    import render_tab_tables

inject_styles()

# ── Session state defaults — ALL keys initialised here, once, at startup ──────
_DEFAULTS = dict(
    # App state
    documents=[], chunks=[], findings=[], score_summary={},
    search_results=[], freq_data={}, analysis_done=False,
    company_name="", query_history=[], active_query="", viewer_jump=1,
    backend_kwargs={}, auto_params={},
    extracted_tables=[],
    # Admin state — initialised here so sidebar never reads uninitialised keys
    admin_logged_in=False,
    show_admin_panel=False,
    admin_login_error="",
    llm_restricted=False,
    llm_locked_backend="Ollama (Local)",
    llm_locked_model="llama3",
    llm_locked_url="http://localhost:11434",
    llm_locked_api_key="",
    llm_locked_custom_url="",
)
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# Must run after _DEFAULTS so tab_visibility is set correctly
init_admin_state()

# ── Sidebar ───────────────────────────────────────────────────────────────────
render_sidebar()

# ── Page header ───────────────────────────────────────────────────────────────
st.markdown("""
<div class="da-title">
    <h1>Contract <em>Intelligence</em> Platform</h1>
    <p>Risk detection · Clause analysis · Legal intelligence for multinational deal documentation</p>
</div>""", unsafe_allow_html=True)

if st.session_state.documents:
    loaded = [d for d in st.session_state.documents if not d.get("error")]
    n_findings = len(st.session_state.findings)
    finding_note = f" · {n_findings} finding(s)" if n_findings else ""
    st.markdown(
        f'<div style="margin-bottom:22px;">'
        f'<div style="font-size:11px;font-weight:600;text-transform:uppercase;'
        f'letter-spacing:2px;color:#3B82F6;margin-bottom:6px;">'
        f'Active · {len(loaded)} files · {len(st.session_state.chunks)} chunks{finding_note}</div>'
        f'{doc_pills(loaded)}</div>',
        unsafe_allow_html=True,
    )

# ── Admin panel overlay ───────────────────────────────────────────────────────
if st.session_state.show_admin_panel:
    render_admin_panel()

# ── Dynamic tabs ──────────────────────────────────────────────────────────────
_RENDERERS = {
    "analysis":  render_tab_analysis,
    "search":    render_tab_search,
    "query":     render_tab_query,
    "viewer":    render_tab_viewer,
    "dashboard": render_tab_dashboard,
    "reports":   render_tab_reports,
    "tables":    render_tab_tables,
    "debug":     render_tab_debug,
}

visible = get_visible_tabs()

if not visible:
    st.warning("No tabs are currently enabled. Open the admin panel to enable tabs.")
else:
    tab_objects = st.tabs([t["label"] for t in visible])
    for tab_obj, tab in zip(tab_objects, visible):
        with tab_obj:
            _RENDERERS[tab["key"]]()

st.markdown(
    '<div class="da-footer">DealAnalyzer — Contract Intelligence · '
    'All AI analysis must be reviewed by qualified legal counsel.</div>',
    unsafe_allow_html=True,
)