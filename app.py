"""
Deal Analyzer — Contract Intelligence Platform
Run: streamlit run app.py
"""

import streamlit as st
import pandas as pd
import re, json
from datetime import datetime
from html import escape as html_escape

from modules.document_handler import batch_load_documents
from modules.chunker import chunk_all_documents, auto_chunk_params
from modules.llm_backend import (LLMBackend, BACKEND_OLLAMA, BACKEND_MISTRAL,
                                  BACKEND_CUSTOM, BACKEND_ANTHROPIC)
from modules.analyzer import (RISK_CATEGORIES, build_analysis_prompt,
                               parse_llm_risk_response, keyword_scan_chunk, score_findings)
from modules.search import (keyword_search, get_keyword_frequencies,
                             build_query_prompt, simple_relevance_search)
from modules.reporter import generate_pdf_report, generate_excel_report
from modules.visualizer import (plot_keyword_frequency, plot_risk_distribution,
                                 plot_category_breakdown, plot_keyword_heatmap,
                                 plot_document_stats)

# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="Deal Analyzer | Contract Intelligence",
                   page_icon="⚖️", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&family=Roboto+Mono:wght@400;500&display=swap');

html, body, [class*="css"], .stApp, .stMarkdown, .stText,
button, input, select, textarea { font-family: 'Roboto', sans-serif !important; }
code, pre { font-family: 'Roboto Mono', monospace !important; }

section[data-testid="stSidebar"] { border-right: 3px solid #3B82F6; }

.da-logo { display:flex; align-items:center; gap:10px;
           padding:6px 0 18px 0; border-bottom:1px solid rgba(59,130,246,0.25);
           margin-bottom:18px; }
.da-logo-icon { width:38px; height:38px;
                background:linear-gradient(135deg,#3B82F6,#0EA5E9);
                border-radius:9px; display:flex; align-items:center;
                justify-content:center; font-size:20px; }
.da-logo h2 { font-size:16px; font-weight:700; margin:0; line-height:1.2; }
.da-logo small { font-size:10px; opacity:.5; text-transform:uppercase; letter-spacing:1.5px; }

.da-title { margin-bottom:28px; padding-bottom:16px; border-bottom:2px solid #3B82F6; }
.da-title h1 { font-size:30px; font-weight:700; margin:0 0 4px; letter-spacing:-.5px; }
.da-title h1 em { font-style:normal; color:#3B82F6; }
.da-title p { margin:0; font-size:13px; opacity:.5; font-weight:300; }

.da-sec { font-size:10px; font-weight:600; text-transform:uppercase; letter-spacing:2px;
          color:#3B82F6; margin-bottom:14px; display:flex; align-items:center; gap:8px; }
.da-sec::after { content:''; flex:1; height:1px; background:rgba(59,130,246,0.2); }

.badge { display:inline-block; padding:2px 9px; border-radius:12px;
         font-size:11px; font-weight:600; letter-spacing:.5px; }
.badge-HIGH   { background:#FEE2E2; color:#B91C1C; border:1px solid #FECACA; }
.badge-MEDIUM { background:#FEF3C7; color:#92400E; border:1px solid #FDE68A; }
.badge-LOW    { background:#DCFCE7; color:#166534; border:1px solid #BBF7D0; }

.fc { border-radius:10px; border:1px solid rgba(0,0,0,.08); padding:16px 18px;
      margin-bottom:12px; border-left:4px solid #94A3B8;
      background:rgba(59,130,246,.03); }
.fc-HIGH   { border-left-color:#EF4444; }
.fc-MEDIUM { border-left-color:#F59E0B; }
.fc-LOW    { border-left-color:#22C55E; }
.fc-hdr  { display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin-bottom:10px; }
.fc-cat  { font-weight:600; font-size:13px; }
.fc-src  { font-size:11px; opacity:.5; font-family:'Roboto Mono',monospace;
           background:rgba(0,0,0,.05); padding:1px 6px; border-radius:4px; }
.fc-ln   { font-size:11px; color:#3B82F6; font-family:'Roboto Mono',monospace; }
.fc-find { font-size:13px; font-weight:500; margin-bottom:8px; line-height:1.5; }
.fc-quote { font-family:'Roboto Mono',monospace; font-size:12px;
            background:rgba(59,130,246,.07); border-left:3px solid #3B82F6;
            padding:8px 12px; margin:8px 0; border-radius:0 6px 6px 0;
            word-break:break-word; line-height:1.6; }
.fc-interp { font-size:13px; line-height:1.65; opacity:.75; }
.fc-qlbl { font-size:10px; font-weight:600; text-transform:uppercase;
           letter-spacing:1.5px; color:#3B82F6; margin:10px 0 6px; }
.fc-qi   { font-size:12px; line-height:1.6; opacity:.7;
           padding:3px 0 3px 14px; position:relative; }
.fc-qi::before { content:'→'; position:absolute; left:0; color:#3B82F6; }

/* Search result */
.sr { border-radius:8px; padding:0; margin-bottom:14px;
      border:1px solid rgba(0,0,0,.08); overflow:hidden; }
.sr-hdr { background:rgba(59,130,246,.06); padding:10px 14px;
          border-bottom:1px solid rgba(59,130,246,.12);
          display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
.sr-doc { font-weight:700; font-size:13px; }
.sr-ln  { font-size:11px; font-family:'Roboto Mono',monospace;
          color:#0EA5E9; background:rgba(14,165,233,.1);
          padding:2px 7px; border-radius:10px; }
.sr-cnt { font-size:11px; background:rgba(0,0,0,.06);
          padding:2px 7px; border-radius:10px; }
.sr-kw  { font-size:11px; background:rgba(245,158,11,.15); color:#92400E;
          padding:2px 7px; border-radius:10px; border:1px solid rgba(245,158,11,.25); }
.sr-body { padding:12px 14px; }
.sr-match { margin-bottom:10px; border-left:2px solid #E2E8F0; padding-left:12px; }
.sr-match:last-child { margin-bottom:0; }
.sr-match-kw { font-size:10px; font-weight:600; text-transform:uppercase;
               letter-spacing:1px; color:#64748B; margin-bottom:4px; }
.sr-ctx { font-size:13px; line-height:1.75; word-break:break-word; }
.sr-ctx mark { background:#FEF08A; color:#713F12; border-radius:2px;
               padding:0 2px; font-weight:600; }

/* LLM query */
.q-bub { padding:12px 16px; border-radius:8px; background:rgba(59,130,246,.07);
         border-left:3px solid #3B82F6; font-size:14px; font-weight:500;
         margin-bottom:10px; }
.a-bub { padding:16px 20px; border-radius:8px; border:1px solid rgba(0,0,0,.08);
         background:rgba(20,184,166,.04); border-left:3px solid #14B8A6;
         font-size:13px; line-height:1.75; }
.a-lbl { font-size:10px; text-transform:uppercase; letter-spacing:1.5px;
         font-weight:600; color:#14B8A6; margin-bottom:8px; }

/* Metric */
.mc { border-radius:10px; border:1px solid rgba(0,0,0,.08);
      padding:16px; text-align:center; }
.mc-v { font-size:36px; font-weight:700; line-height:1; margin-bottom:4px; }
.mc-l { font-size:11px; text-transform:uppercase; letter-spacing:1.5px; opacity:.5; }
.mc-HIGH   .mc-v { color:#EF4444; }
.mc-MEDIUM .mc-v { color:#F59E0B; }
.mc-LOW    .mc-v { color:#22C55E; }
.mc-blue   .mc-v { color:#3B82F6; }

.dp { display:inline-flex; align-items:center; gap:5px; font-size:12px;
      padding:3px 10px; border-radius:14px;
      background:rgba(59,130,246,.08); border:1px solid rgba(59,130,246,.2); margin:2px; }

.info-strip { padding:10px 14px; border-radius:8px; font-size:13px;
              background:rgba(59,130,246,.06); border:1px solid rgba(59,130,246,.15);
              margin-bottom:16px; line-height:1.6; }
.auto-badge { display:inline-flex; align-items:center; gap:6px; padding:6px 12px;
              border-radius:6px; font-size:12px; background:rgba(20,184,166,.1);
              border:1px solid rgba(20,184,166,.25); color:#0D9488; }

/* Document viewer */
.doc-page { background:rgba(0,0,0,.025); border:1px solid rgba(0,0,0,.07);
            border-radius:8px; padding:16px 20px; margin-bottom:12px;
            font-size:13px; line-height:1.85; white-space:pre-wrap;
            word-break:break-word; font-family:'Roboto Mono',monospace; }
.doc-page-hdr { font-size:11px; font-weight:600; text-transform:uppercase;
                letter-spacing:1.5px; color:#3B82F6; margin-bottom:8px; }

.empty-state { text-align:center; padding:56px 24px; opacity:.5; }
.empty-state .es-icon { font-size:48px; margin-bottom:14px; }
.empty-state h3 { font-size:18px; font-weight:600; margin-bottom:8px; }
.empty-state p  { font-size:13px; line-height:1.6; max-width:360px; margin:0 auto; }

.da-footer { margin-top:48px; padding-top:16px; text-align:center;
             border-top:1px solid rgba(0,0,0,.08); font-size:12px; opacity:.4; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════
def _init():
    for k, v in dict(
        documents=[], chunks=[], findings=[], score_summary={},
        search_results=[], freq_data={}, analysis_done=False,
        company_name="", query_history=[], active_query=""
    ).items():
        if k not in st.session_state: st.session_state[k] = v
_init()


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def _clean(t): return re.sub(r'<[^>]+>', '', t or '').strip()

def _highlight(text: str, keywords: list) -> str:
    out = html_escape(text)
    for kw in keywords:
        out = re.sub(re.escape(html_escape(kw)),
                     lambda m: f"<mark>{m.group()}</mark>", out, flags=re.IGNORECASE)
    return out

def _badge(level): return f'<span class="badge badge-{level}">{level}</span>'
def _mc(val, label, cls="mc-blue"):
    return f'<div class="mc {cls}"><div class="mc-v">{val}</div><div class="mc-l">{label}</div></div>'
def _pills(docs):
    icons = {"pdf":"📄","docx":"📝","doc":"📝","xlsx":"📊","xls":"📊"}
    out = "".join(f'<span class="dp">{icons.get(d.get("type",""),"📎")} {html_escape(d["filename"])}</span>'
                  for d in docs[:8])
    if len(docs) > 8: out += f'<span class="dp">+{len(docs)-8} more</span>'
    return out


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("""
    <div class="da-logo">
        <div class="da-logo-icon">⚖</div>
        <div><h2>DealAnalyzer</h2><small>Contract Intelligence</small></div>
    </div>""", unsafe_allow_html=True)

    # ── FILE UPLOAD — top of sidebar ─────────────────────────────────────────
    st.markdown("**📂 Upload Documents**")
    uploaded_files = st.file_uploader(
        "PDF · Word · Excel", type=["pdf","docx","doc","xlsx","xls"],
        accept_multiple_files=True, label_visibility="collapsed"
    )

    # ── AI BACKEND ────────────────────────────────────────────────────────────
    st.markdown("**🤖 AI Backend**")
    backend_type = st.selectbox("Backend",
        [BACKEND_OLLAMA, BACKEND_MISTRAL, BACKEND_ANTHROPIC, BACKEND_CUSTOM],
        label_visibility="collapsed")
    bkw = {"backend_type": backend_type}

    model_name = ""
    if backend_type == BACKEND_OLLAMA:
        bkw["ollama_url"]   = st.text_input("Ollama URL", "http://localhost:11434")
        bkw["ollama_model"] = st.selectbox("Model",
            ["llama3","llama3.1","llama3.2","mistral","mixtral","phi3","llama2"])
        model_name = bkw["ollama_model"]
    elif backend_type == BACKEND_MISTRAL:
        bkw["mistral_api_key"] = st.text_input("API Key", type="password")
        bkw["mistral_model"]   = st.selectbox("Model",
            ["codestral-latest","mistral-large-latest","mistral-medium-latest","mistral-small-latest","open-mixtral-8x22b"])
        model_name = bkw["mistral_model"]
    elif backend_type == BACKEND_ANTHROPIC:
        bkw["anthropic_api_key"] = st.text_input("API Key", type="password")
        bkw["anthropic_model"]   = st.selectbox("Model",
            ["claude-sonnet-4-20250514","claude-3-5-sonnet-20241022","claude-3-opus-20240229","claude-3-haiku-20240307"])
        model_name = bkw["anthropic_model"]
    elif backend_type == BACKEND_CUSTOM:
        bkw["custom_url"]     = st.text_input("Endpoint URL")
        bkw["custom_api_key"] = st.text_input("API Key (optional)", type="password")
        bkw["custom_model"]   = st.text_input("Model ID")
        model_name = bkw.get("custom_model","")

    bkw["temperature"] = 0.2
    auto_params = auto_chunk_params(backend_type, model_name)

    # ── CHUNKING MODE ─────────────────────────────────────────────────────────
    st.markdown("**⚙ Document Chunking**")
    chunk_mode = st.radio("Mode", ["🤖 Auto (Intelligent)", "✏ Manual"],
                          horizontal=True, label_visibility="collapsed")

    if chunk_mode == "🤖 Auto (Intelligent)":
        final_params = auto_params
        bkw["max_tokens"] = auto_params["max_tokens"]
        st.markdown(f'<div class="auto-badge">⚙ {auto_params["label"]}</div>',
                    unsafe_allow_html=True)
    else:
        cs = st.slider("Chunk Size (chars)", 200, 2000, auto_params["chunk_size"], 50,
                        help="How many characters per chunk")
        ov = st.slider("Overlap (chars)",    0,   400, auto_params["overlap"],     25,
                        help="Characters shared between adjacent chunks")
        mt = st.select_slider("Max Response Tokens", [512,1024,2048,3072,4096],
                               value=auto_params["max_tokens"])
        final_params = {"chunk_size": cs, "overlap": ov, "max_tokens": mt}
        bkw["max_tokens"] = mt

    st.session_state.backend_kwargs = bkw
    st.session_state.auto_params    = final_params

    # ── LOAD BUTTON ───────────────────────────────────────────────────────────
    if uploaded_files:
        if st.button("Load Documents", use_container_width=True, type="primary"):
            with st.spinner(f"Loading {len(uploaded_files)} file(s)…"):
                docs   = batch_load_documents(uploaded_files)
                chunks = chunk_all_documents(docs, final_params["chunk_size"],
                                             final_params["overlap"])
            st.session_state.update(
                documents=docs, chunks=chunks,
                findings=[], score_summary={}, search_results=[],
                freq_data={}, analysis_done=False
            )
            loaded = [d for d in docs if not d.get("error")]
            failed = [d for d in docs if  d.get("error")]
            st.success(f"✓ {len(loaded)} doc(s) · {len(chunks)} chunks")
            for f in failed: st.error(f"✗ {f['filename']}: {f['error']}")

    st.divider()
    st.markdown("**Project / Matter**")
    st.session_state.company_name = st.text_input(
        "Company", value=st.session_state.company_name,
        placeholder="e.g. Acme Corp — Series B", label_visibility="collapsed")

    if st.button("🔌 Test Connection", use_container_width=True):
        with st.spinner("Testing…"):
            ok = LLMBackend(**bkw).test_connection()
        (st.success("✓ Connected") if ok else st.error("Connection failed"))


# ══════════════════════════════════════════════════════════════════════════════
# HEADER + DOC STATUS
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="da-title">
    <h1>Contract <em>Intelligence</em> Platform</h1>
    <p>Risk detection · Clause analysis · Legal intelligence for multinational deal documentation</p>
</div>""", unsafe_allow_html=True)

if st.session_state.documents:
    loaded = [d for d in st.session_state.documents if not d.get("error")]
    st.markdown(
        f'<div style="margin-bottom:22px;">'
        f'<div style="font-size:11px;font-weight:600;text-transform:uppercase;'
        f'letter-spacing:2px;color:#3B82F6;margin-bottom:6px;">'
        f'Active · {len(loaded)} files · {len(st.session_state.chunks)} chunks</div>'
        f'{_pills(loaded)}</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════
(t_analysis, t_search, t_query,
 t_viewer, t_dashboard, t_reports) = st.tabs([
    "⚖ Risk Analysis",
    "🔍 Document Search",
    "💬 LLM Query",
    "📄 Document Viewer",
    "📊 Analytics",
    "📑 Export Reports",
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — RISK ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
with t_analysis:
    st.markdown('<div class="da-sec">⚖ Contractual Risk Detection · AI-Powered</div>',
                unsafe_allow_html=True)
    if not st.session_state.documents:
        st.markdown('<div class="empty-state"><div class="es-icon">⚖</div>'
                    '<h3>No Documents Loaded</h3>'
                    '<p>Upload documents via the sidebar.</p></div>', unsafe_allow_html=True)
    else:
        st.markdown("**Select risk categories to detect:**")
        cols = st.columns(3)
        selected_cats = []
        for i, (ck, ci) in enumerate(RISK_CATEGORIES.items()):
            with cols[i % 3]:
                if st.checkbox(ci["label"], value=True, key=f"cat_{ck}"):
                    selected_cats.append(ck)

        st.markdown('<div class="info-strip">💡 Documents are <strong>keyword-scanned first</strong> '
                    '(no API cost), then only suspicious sections are sent to the LLM for deep analysis.'
                    '</div>', unsafe_allow_html=True)

        if st.button("🚀 Run Risk Analysis", type="primary", disabled=not selected_cats):
            if "backend_kwargs" not in st.session_state:
                st.error("Configure AI backend in the sidebar first.")
            else:
                backend = LLMBackend(**st.session_state.backend_kwargs)
                pre = [(ch, {k:v for k,v in keyword_scan_chunk(ch["text"]).items()
                              if k in selected_cats})
                       for ch in st.session_state.chunks]
                pre = [(ch,h) for ch,h in pre if h]
                if not pre:
                    st.warning("No chunks matched risk keyword patterns.")
                else:
                    total = sum(len(h) for _,h in pre)
                    st.info(f"Keyword scan done — {total} clause segments to analyse…")
                    findings, prog, stat = [], st.progress(0), st.empty()
                    n = 0
                    for chunk, hit_cats in pre:
                        for category in hit_cats:
                            stat.caption(f"Analysing {chunk['filename']} · "
                                         f"lines {chunk.get('start_line','?')}–{chunk.get('end_line','?')} · "
                                         f"{RISK_CATEGORIES[category]['label']}")
                            res = backend.query(build_analysis_prompt(chunk["text"], category))
                            if res.get("error"):
                                st.warning(f"LLM error: {res['error']}")
                            elif res.get("response"):
                                f = parse_llm_risk_response(res["response"], chunk, category)
                                if f:
                                    f["start_line"] = chunk.get("start_line","?")
                                    f["end_line"]   = chunk.get("end_line","?")
                                    findings.append(f)
                            n += 1
                            prog.progress(min(n/max(total,1), 1.0))
                    prog.progress(1.0); stat.empty()
                    st.session_state.findings     = findings
                    st.session_state.score_summary= score_findings(findings)
                    st.session_state.analysis_done= True
                    st.success(f"✓ Analysis complete — {len(findings)} findings.")

        if st.session_state.analysis_done and st.session_state.score_summary:
            s = st.session_state.score_summary
            ov = s.get("overall_risk","LOW")
            m1,m2,m3,m4,m5 = st.columns(5)
            for col, val, lbl, cls in [
                (m1, ov,               "Overall Risk",  f"mc-{ov}"),
                (m2, s.get("total",0), "Total",         "mc-blue"),
                (m3, s.get("high",0),  "High Risk",     "mc-HIGH"),
                (m4, s.get("medium",0),"Medium Risk",   "mc-MEDIUM"),
                (m5, s.get("low",0),   "Low Risk",      "mc-LOW"),
            ]:
                with col: st.markdown(_mc(val, lbl, cls), unsafe_allow_html=True)
            st.markdown("")

        if st.session_state.findings:
            st.markdown("---")
            fc1,fc2,fc3 = st.columns(3)
            with fc1:
                f_risk = st.multiselect("Risk Level", ["HIGH","MEDIUM","LOW"],
                                         default=["HIGH","MEDIUM","LOW"])
            with fc2:
                f_cat = st.multiselect("Category", list(RISK_CATEGORIES.keys()),
                                        format_func=lambda k: RISK_CATEGORIES[k]["label"],
                                        default=list(RISK_CATEGORIES.keys()))
            with fc3:
                all_docs = list(set(f["filename"] for f in st.session_state.findings))
                f_doc = st.multiselect("Document", all_docs, default=all_docs)

            filtered = [f for f in st.session_state.findings
                        if f.get("risk_level") in f_risk
                        and f.get("category")   in f_cat
                        and f.get("filename")   in f_doc]
            st.caption(f"Showing {len(filtered)} of {len(st.session_state.findings)} findings")

            for finding in filtered:
                risk  = finding.get("risk_level","LOW")
                cat   = _clean(finding.get("category_label",""))
                fname = html_escape(finding.get("filename",""))
                sl, el= finding.get("start_line","?"), finding.get("end_line","?")
                txt   = _clean(finding.get("finding",""))
                prob  = _clean(finding.get("problematic_language",""))
                interp= _clean(finding.get("interpretation",""))
                qs    = [_clean(q) for q in finding.get("follow_up_questions",[]) if q]

                quote_html = (f'<div class="fc-quote">{html_escape(prob)}</div>'
                              if prob and prob.upper() not in ("N/A","") else "")
                qs_html = ""
                if qs:
                    items = "".join(f'<div class="fc-qi">{html_escape(q)}</div>' for q in qs)
                    qs_html = f'<div class="fc-qlbl">Legal Team Follow-up Questions</div>{items}'

                st.markdown(f"""
                <div class="fc fc-{risk}">
                  <div class="fc-hdr">
                    {_badge(risk)}
                    <span class="fc-cat">{html_escape(cat)}</span>
                    <span class="fc-src">{fname}</span>
                    <span class="fc-ln">Lines {sl}–{el}</span>
                  </div>
                  <div class="fc-find">{html_escape(txt)}</div>
                  {quote_html}
                  <div class="fc-interp">{html_escape(interp)}</div>
                  {qs_html}
                </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — DOCUMENT SEARCH  (fixed line numbers + rich context)
# ══════════════════════════════════════════════════════════════════════════════
with t_search:
    st.markdown('<div class="da-sec">🔍 Keyword & Context Search · Multi-Document</div>',
                unsafe_allow_html=True)
    if not st.session_state.chunks:
        st.markdown('<div class="empty-state"><div class="es-icon">🔍</div>'
                    '<h3>No Documents Loaded</h3></div>', unsafe_allow_html=True)
    else:
        sc1, sc2 = st.columns([4, 1])
        with sc1:
            kw_input = st.text_input(
                "Keywords (comma-separated)",
                placeholder="e.g. indemnify, royalty, automatic renewal, sole discretion",
                label_visibility="collapsed")
        with sc2:
            run_search = st.button("🔍 Search", use_container_width=True, type="primary")
        cs_check = st.checkbox("Case-sensitive match", value=False)

        if run_search and kw_input.strip():
            kws = [k.strip() for k in kw_input.split(",") if k.strip()]
            with st.spinner("Searching…"):
                results = keyword_search(st.session_state.chunks, kws, cs_check)
                freq    = get_keyword_frequencies(st.session_state.chunks, kws)
            st.session_state.search_results = results
            st.session_state.freq_data      = freq
            st.session_state.last_keywords  = kws

        if st.session_state.search_results:
            results   = st.session_state.search_results
            kws       = st.session_state.get("last_keywords", [])
            total_occ = sum(r.get("total_hits", 0) for r in results)

            st.markdown(
                f"**{len(results)} sections matched · {total_occ} total occurrences** "
                f"across all documents")
            st.markdown("")

            for r in results[:30]:
                fname       = html_escape(r.get("filename", ""))
                total_hits  = r.get("total_hits", 0)
                matched_kws = r.get("matched_keywords", [])
                snippets    = r.get("match_snippets", [])

                # ── Exact line numbers: one badge per unique match line ───
                exact_lines = r.get("exact_lines", [])
                if exact_lines:
                    if len(exact_lines) == 1:
                        line_display = f"Line {exact_lines[0]}"
                    elif len(exact_lines) <= 6:
                        line_display = "Lines " + ", ".join(str(l) for l in exact_lines)
                    else:
                        # Many hits — show range + count
                        line_display = (f"Lines {exact_lines[0]}–{exact_lines[-1]} "
                                        f"({len(exact_lines)} matches)")
                else:
                    line_display = "Line ?"

                kw_badges = " ".join(
                    f'<span class="sr-kw">{html_escape(k)}</span>' for k in matched_kws
                )

                # ── Build one block per match occurrence ─────────────────
                match_blocks = ""
                seen = set()
                for s in snippets:
                    key = (s["keyword"], s["exact_line"])
                    if key in seen:
                        continue
                    seen.add(key)
                    raw  = s.get("snippet", "")
                    high = _highlight(raw, matched_kws)
                    ln   = s.get("exact_line", "?")
                    kw   = html_escape(s.get("keyword", ""))
                    match_blocks += (
                        f'<div class="sr-match">'
                        f'<div class="sr-match-kw">'
                        f'  Keyword: <strong>"{kw}"</strong>'
                        f'  &nbsp;·&nbsp; '
                        f'  <span style="color:#3B82F6;font-family:\'Roboto Mono\',monospace;">'
                        f'Line {ln}</span>'
                        f'</div>'
                        f'<div class="sr-ctx">…{high}…</div>'
                        f'</div>'
                    )

                st.markdown(f"""
                <div class="sr">
                  <div class="sr-hdr">
                    <span class="sr-doc">📄 {fname}</span>
                    <span class="sr-ln">{line_display}</span>
                    <span class="sr-cnt">×{total_hits} occurrence(s)</span>
                    {kw_badges}
                  </div>
                  <div class="sr-body">{match_blocks}</div>
                </div>""", unsafe_allow_html=True)

            if len(results) > 30:
                st.caption(f"Top 30 shown of {len(results)}. Export full results from the Reports tab.")
        elif run_search:
            st.warning("No matches found. Try different keywords.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — LLM QUERY
# ══════════════════════════════════════════════════════════════════════════════
with t_query:
    st.markdown('<div class="da-sec">💬 Natural Language Query · RAG-Powered</div>',
                unsafe_allow_html=True)
    if not st.session_state.chunks:
        st.markdown('<div class="empty-state"><div class="es-icon">💬</div>'
                    '<h3>No Documents Loaded</h3></div>', unsafe_allow_html=True)
    else:
        EXAMPLES = [
            "What are the termination rights of each party?",
            "Are there any automatic renewal or evergreen clauses?",
            "What royalty or fee structures are defined?",
            "What indemnification obligations does the buyer carry?",
            "What are the governing law and dispute resolution provisions?",
            "Are there non-compete or exclusivity restrictions?",
        ]
        with st.expander("💡 Example questions — click to populate"):
            ec = st.columns(2)
            for i, eq in enumerate(EXAMPLES):
                with ec[i % 2]:
                    if st.button(eq, key=f"eq_{i}", use_container_width=True):
                        st.session_state.active_query = eq
                        st.rerun()

        user_q = st.text_area("Your question", value=st.session_state.active_query,
                               placeholder="Type or click an example above…",
                               height=90, label_visibility="collapsed")
        st.session_state.active_query = user_q

        qc1, qc2 = st.columns([1,5])
        with qc1:
            top_k = st.selectbox("Context chunks", [3,5,6,8,10], index=1)
        with qc2:
            st.markdown("<div style='padding-top:22px'></div>", unsafe_allow_html=True)
            submit_q = st.button("💬 Ask Question", type="primary")

        if submit_q:
            question = st.session_state.active_query.strip()
            if not question:
                st.warning("Please type or select a question first.")
            elif "backend_kwargs" not in st.session_state:
                st.error("Configure the AI backend in the sidebar.")
            else:
                with st.spinner("Retrieving context and generating answer…"):
                    relevant = simple_relevance_search(st.session_state.chunks, question, top_k)
                    prompt   = build_query_prompt(question, relevant)
                    result   = LLMBackend(**st.session_state.backend_kwargs).query(prompt)
                if result.get("error"):
                    st.error(f"LLM Error: {result['error']}")
                else:
                    st.session_state.query_history.append({
                        "question": question,
                        "response": result.get("response",""),
                        "chunks":   len(relevant),
                        "ts":       datetime.now().strftime("%H:%M"),
                    })
                    st.session_state.active_query = ""
                    st.rerun()

        if st.session_state.query_history:
            st.markdown("---")
            for item in reversed(st.session_state.query_history):
                st.markdown(f'<div class="q-bub">Q: {html_escape(item["question"])}</div>',
                            unsafe_allow_html=True)
                resp = html_escape(item["response"]).replace("\n","<br>")
                st.markdown(f'<div class="a-bub"><div class="a-lbl">⚖ AI Analysis · '
                            f'{item["ts"]} · {item["chunks"]} sections</div>{resp}</div>',
                            unsafe_allow_html=True)
                st.markdown("")
            if st.button("🗑 Clear History"):
                st.session_state.query_history = []; st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — DOCUMENT VIEWER  (NEW)
# ══════════════════════════════════════════════════════════════════════════════
with t_viewer:
    st.markdown('<div class="da-sec">📄 Document Viewer · Full Document Text</div>',
                unsafe_allow_html=True)

    if not st.session_state.documents:
        st.markdown('<div class="empty-state"><div class="es-icon">📄</div>'
                    '<h3>No Documents Loaded</h3>'
                    '<p>Upload documents via the sidebar to view their contents here.</p>'
                    '</div>', unsafe_allow_html=True)
    else:
        docs = [d for d in st.session_state.documents if not d.get("error")]
        if not docs:
            st.error("All uploaded documents failed to load.")
        else:
            # ── Document selector ───────────────────────────────────────────
            doc_names = [d["filename"] for d in docs]
            selected_doc = st.selectbox("Select document to view", doc_names,
                                         label_visibility="visible")
            doc = next((d for d in docs if d["filename"] == selected_doc), None)

            if doc:
                raw   = doc.get("raw_text","")
                pages = doc.get("pages",[])
                meta  = doc.get("metadata",{})
                words = len(raw.split())
                chars = len(raw)
                lines = raw.count("\n") + 1

                # ── Stats strip ─────────────────────────────────────────────
                vs1,vs2,vs3,vs4 = st.columns(4)
                for col, val, lbl in [
                    (vs1, doc.get("type","").upper(),  "Format"),
                    (vs2, f"{words:,}",                "Words"),
                    (vs3, f"{chars:,}",                "Characters"),
                    (vs4, lines,                       "Lines"),
                ]:
                    with col: st.markdown(_mc(val, lbl), unsafe_allow_html=True)
                st.markdown("")

                # ── View mode ──────────────────────────────────────────────
                view_mode = st.radio("View as",
                    ["📄 Full Text", "📑 Page / Section View", "🔢 Line-Numbered"],
                    horizontal=True, label_visibility="collapsed")

                # Optional search-within highlight
                sv_kw = st.text_input("🔍 Highlight within document (optional)",
                                       placeholder="e.g. indemnify",
                                       label_visibility="collapsed")

                st.markdown("---")

                if view_mode == "📄 Full Text":
                    display_text = raw
                    if sv_kw.strip():
                        # Render with highlights via markdown code hack — use st.markdown
                        highlighted = _highlight(display_text[:50000], [sv_kw.strip()])
                        st.markdown(
                            f'<div class="doc-page" style="max-height:70vh;overflow-y:auto;">'
                            f'{highlighted}</div>',
                            unsafe_allow_html=True)
                    else:
                        st.markdown(
                            f'<div class="doc-page" style="max-height:70vh;overflow-y:auto;">'
                            f'{html_escape(display_text[:60000])}'
                            + ("<br><em>[Truncated to 60,000 chars — download full file for complete text]</em>"
                               if len(display_text) > 60000 else "")
                            + '</div>',
                            unsafe_allow_html=True)

                elif view_mode == "📑 Page / Section View":
                    if not pages:
                        st.info("No page/section data available for this document type.")
                    else:
                        st.caption(f"{len(pages)} sections/pages")
                        for pg in pages:
                            num  = pg.get("page_number", "?")
                            text = pg.get("text","").strip()
                            if not text: continue
                            if sv_kw.strip():
                                body = _highlight(html_escape(text), [sv_kw.strip()])
                            else:
                                body = html_escape(text)
                            with st.expander(f"{'Page' if isinstance(num,int) else 'Sheet'} {num} "
                                             f"— {len(text.split())} words"):
                                st.markdown(
                                    f'<div class="doc-page">{body}</div>',
                                    unsafe_allow_html=True)

                elif view_mode == "🔢 Line-Numbered":
                    all_lines = raw.split("\n")
                    st.caption(f"{len(all_lines)} lines total")

                    # Filter: jump to line
                    jc1, jc2 = st.columns([1,4])
                    with jc1:
                        jump = st.number_input("Jump to line", min_value=1,
                                               max_value=len(all_lines), value=1, step=1)
                    with jc2:
                        show_n = st.select_slider("Lines to show",
                                                   options=[50,100,200,500,1000,"All"], value=100)

                    start_idx = max(0, int(jump) - 1)
                    end_idx   = len(all_lines) if show_n == "All" else min(len(all_lines), start_idx + int(show_n))
                    slice_lines = all_lines[start_idx:end_idx]

                    # Render as monospace with line numbers
                    rendered = ""
                    for i, line in enumerate(slice_lines, start=start_idx + 1):
                        safe_line = html_escape(line) if not sv_kw.strip() else \
                                    _highlight(html_escape(line), [sv_kw.strip()])
                        ln_style = "color:#3B82F6;user-select:none;margin-right:12px;min-width:42px;display:inline-block;text-align:right;font-size:11px;"
                        rendered += f'<span style="{ln_style}">{i}</span>{safe_line}\n'

                    st.markdown(
                        f'<div class="doc-page" style="max-height:65vh;overflow-y:auto;">{rendered}</div>',
                        unsafe_allow_html=True)

                # ── Download original ───────────────────────────────────────
                st.markdown("")
                st.download_button(
                    f"⬇ Download extracted text — {selected_doc}",
                    data=raw, file_name=f"{selected_doc}_extracted.txt",
                    mime="text/plain"
                )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — ANALYTICS
# ══════════════════════════════════════════════════════════════════════════════
with t_dashboard:
    st.markdown('<div class="da-sec">📊 Analytics · Visualizations & Statistics</div>',
                unsafe_allow_html=True)
    has_a = bool(st.session_state.score_summary)
    has_s = bool(st.session_state.freq_data)
    has_d = bool(st.session_state.documents)

    if not has_a and not has_s:
        st.markdown('<div class="empty-state"><div class="es-icon">📊</div>'
                    '<h3>No Data Yet</h3>'
                    '<p>Run a Risk Analysis or Keyword Search first.</p></div>',
                    unsafe_allow_html=True)
    else:
        if has_d:
            docs = [d for d in st.session_state.documents if not d.get("error")]
            total_w = sum(len(d.get("raw_text","").split()) for d in docs)
            total_c = sum(len(d.get("raw_text","")) for d in docs)
            st.markdown("#### Corpus Statistics")
            ts1,ts2,ts3,ts4 = st.columns(4)
            for col, val, lbl in [
                (ts1, len(docs),           "Documents"),
                (ts2, f"{total_w:,}",      "Words"),
                (ts3, f"{total_c:,}",      "Characters"),
                (ts4, len(st.session_state.chunks), "Chunks"),
            ]:
                with col: st.markdown(_mc(val,lbl), unsafe_allow_html=True)
            st.markdown("")
            with st.expander("📋 Per-Document Breakdown"):
                rows = [{"Document":d["filename"],"Type":d.get("type","").upper(),
                         "Words":len(d.get("raw_text","").split()),
                         "Chars":len(d.get("raw_text","")),
                         "Sections":len(d.get("pages",[]))}
                        for d in docs]
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            st.plotly_chart(plot_document_stats(docs), use_container_width=True)

        if has_a:
            st.markdown("#### Risk Analysis")
            rc1,rc2 = st.columns(2)
            with rc1: st.plotly_chart(plot_risk_distribution(st.session_state.score_summary), use_container_width=True)
            with rc2: st.plotly_chart(plot_category_breakdown(st.session_state.score_summary), use_container_width=True)
            if st.session_state.findings:
                st.markdown("#### All Findings Table")
                df_full = pd.DataFrame([{
                    "Risk":   f.get("risk_level",""),
                    "Category":_clean(f.get("category_label","")),
                    "Document":f.get("filename",""),
                    "Lines":  f"{f.get('start_line','?')}–{f.get('end_line','?')}",
                    "Finding":_clean(f.get("finding",""))[:120],
                    "Flagged Language":_clean(f.get("problematic_language",""))[:100],
                    "Interpretation":_clean(f.get("interpretation",""))[:150],
                } for f in st.session_state.findings])
                st.dataframe(df_full, use_container_width=True, hide_index=True,
                             height=min(700, (len(df_full)+1)*38+50))

        if has_s:
            st.markdown("#### Keyword Analytics")
            st.plotly_chart(plot_keyword_frequency(st.session_state.freq_data), use_container_width=True)
            st.plotly_chart(plot_keyword_heatmap(st.session_state.freq_data), use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 6 — EXPORT
# ══════════════════════════════════════════════════════════════════════════════
with t_reports:
    st.markdown('<div class="da-sec">📑 Export & Compliance Reports</div>',
                unsafe_allow_html=True)
    if not st.session_state.analysis_done:
        st.markdown('<div class="empty-state"><div class="es-icon">📑</div>'
                    '<h3>No Analysis to Export</h3>'
                    '<p>Complete a Risk Analysis first.</p></div>', unsafe_allow_html=True)
    else:
        findings = st.session_state.findings
        summ     = st.session_state.score_summary
        company  = st.session_state.company_name or "Confidential"
        ov       = summ.get("overall_risk","LOW")

        rs1,rs2,rs3,rs4,rs5 = st.columns(5)
        for col, val, lbl, cls in [
            (rs1, ov,               "Overall",  f"mc-{ov}"),
            (rs2, summ.get("total",0),"Total",  "mc-blue"),
            (rs3, summ.get("high",0), "High",   "mc-HIGH"),
            (rs4, summ.get("medium",0),"Medium","mc-MEDIUM"),
            (rs5, summ.get("low",0),  "Low",    "mc-LOW"),
        ]:
            with col: st.markdown(_mc(val,lbl,cls), unsafe_allow_html=True)
        st.markdown("---")

        st.markdown("#### Findings Preview")
        for i, f in enumerate(findings, 1):
            risk  = f.get("risk_level","LOW")
            cat   = _clean(f.get("category_label",""))
            fname = f.get("filename","")
            sl,el = f.get("start_line","?"), f.get("end_line","?")
            with st.expander(f"#{i} · {risk} · {cat} · {fname} · Lines {sl}–{el}"):
                c1,c2 = st.columns([1,3])
                with c1:
                    st.markdown(f"**Risk:** {risk}  \n**File:** {fname}  \n**Lines:** {sl}–{el}  \n**Category:** {cat}")
                with c2:
                    st.markdown(f"**Finding:**  \n{_clean(f.get('finding',''))}")
                    prob = _clean(f.get("problematic_language",""))
                    if prob and prob.upper() not in ("N/A",""):
                        st.markdown("**Flagged Language:**")
                        st.code(prob, language=None)
                    st.markdown(f"**Interpretation:**  \n{_clean(f.get('interpretation',''))}")
                    qs = [_clean(q) for q in f.get("follow_up_questions",[]) if q]
                    if qs:
                        st.markdown("**Follow-up Questions:**")
                        for q in qs: st.markdown(f"→ {q}")
        st.markdown("---")

        ec1,ec2 = st.columns(2)
        with ec1:
            st.markdown("#### 📄 PDF Report")
            st.caption("Executive summary, all findings, risk scoring, follow-up questions.")
            if st.button("Generate PDF", use_container_width=True):
                try:
                    with st.spinner("Building PDF…"):
                        pdf = generate_pdf_report(findings, summ, company)
                    st.download_button("⬇ Download PDF", data=pdf,
                        file_name=f"contract_risk_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                        mime="application/pdf", use_container_width=True)
                except ImportError:
                    st.error("Install reportlab: `pip install reportlab`")
                except Exception as e:
                    st.error(f"PDF error: {e}")

        with ec2:
            st.markdown("#### 📊 Excel Report")
            st.caption("Multi-sheet workbook: Summary · Findings · Category Breakdown.")
            if st.button("Generate Excel", use_container_width=True):
                try:
                    with st.spinner("Building Excel…"):
                        xlsx = generate_excel_report(findings, summ)
                    st.download_button("⬇ Download Excel", data=xlsx,
                        file_name=f"contract_risk_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True)
                except Exception as e:
                    st.error(f"Excel error: {e}")

        with st.expander("🔧 Raw JSON Export"):
            json_out = json.dumps({
                "generated_at": datetime.now().isoformat(), "company": company,
                "summary": summ,
                "findings": [{k: _clean(v) if isinstance(v,str) else v
                              for k,v in f.items()} for f in findings]
            }, indent=2)
            st.code(json_out, language="json")
            st.download_button("⬇ Download JSON", data=json_out,
                               file_name=f"findings_{datetime.now().strftime('%Y%m%d')}.json",
                               mime="application/json")

st.markdown('<div class="da-footer">DealAnalyzer — Contract Intelligence · '
            'All AI analysis must be reviewed by qualified legal counsel.</div>',
            unsafe_allow_html=True)