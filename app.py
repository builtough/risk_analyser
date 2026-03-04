"""
DealAnalyzer — Contract Intelligence Platform
Run: streamlit run app.py
"""
import streamlit as st
from html import escape as html_escape

st.set_page_config(
    page_title="DealAnalyzer | Contract Intelligence",
    page_icon="⚖️", layout="wide", initial_sidebar_state="expanded",
)

from modules.ui.styles        import inject_styles
from modules.ui.helpers       import doc_pills
from modules.ui.sidebar       import render_sidebar
from modules.ui.tab_analysis  import render_tab_analysis
from modules.ui.tab_search    import render_tab_search
from modules.ui.tab_query     import render_tab_query
from modules.ui.tab_viewer    import render_tab_viewer
from modules.ui.tab_dashboard import render_tab_dashboard
from modules.ui.tab_reports   import render_tab_reports

inject_styles()

_DEFAULTS = dict(
    documents=[], chunks=[], findings=[], score_summary={},
    search_results=[], freq_data={}, analysis_done=False,
    company_name="", query_history=[], active_query="", viewer_jump=1,
)
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

render_sidebar()

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

(t_analysis, t_search, t_query,
 t_viewer, t_dashboard, t_reports) = st.tabs([
    "⚖ Risk Analysis", "🔍 Document Search", "💬 LLM Query",
    "📄 Document Viewer", "📊 Analytics", "📑 Export Reports",
])

with t_analysis:  render_tab_analysis()
with t_search:    render_tab_search()
with t_query:     render_tab_query()
with t_viewer:    render_tab_viewer()
with t_dashboard: render_tab_dashboard()
with t_reports:   render_tab_reports()

st.markdown(
    '<div class="da-footer">DealAnalyzer — Contract Intelligence · '
    'All AI analysis must be reviewed by qualified legal counsel.</div>',
    unsafe_allow_html=True,
)