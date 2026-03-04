"""Sidebar — file upload, backend config, chunking, load button."""
import streamlit as st
from modules.document_handler import batch_load_documents
from modules.chunker import chunk_all_documents, auto_chunk_params
from modules.llm_backend import (LLMBackend, BACKEND_OLLAMA, BACKEND_MISTRAL,
                                  BACKEND_ANTHROPIC, BACKEND_CUSTOM)


def render_sidebar():
    """Renders the full sidebar. Returns (backend_kwargs, chunk_params)."""
    with st.sidebar:
        st.markdown("""
        <div class="da-logo">
            <div class="da-logo-icon">⚖</div>
            <div><h2>DealAnalyzer</h2><small>Contract Intelligence</small></div>
        </div>""", unsafe_allow_html=True)

        # ── File Upload ──────────────────────────────────────────────────────
        st.markdown("**📂 Upload Documents**")
        uploaded_files = st.file_uploader(
            "PDF · Word · Excel", type=["pdf", "docx", "doc", "xlsx", "xls"],
            accept_multiple_files=True, label_visibility="collapsed",
        )

        # ── AI Backend ───────────────────────────────────────────────────────
        st.markdown("**🤖 AI Backend**")
        backend_type = st.selectbox(
            "Backend", [BACKEND_OLLAMA, BACKEND_MISTRAL, BACKEND_ANTHROPIC, BACKEND_CUSTOM],
            label_visibility="collapsed",
        )
        bkw = {"backend_type": backend_type}
        model_name = ""

        if backend_type == BACKEND_OLLAMA:
            bkw["ollama_url"]   = st.text_input("Ollama URL", "http://localhost:11434")
            bkw["ollama_model"] = st.selectbox(
                "Model", ["llama3","llama3.1","llama3.2","mistral","mixtral","phi3","llama2"])
            model_name = bkw["ollama_model"]

        elif backend_type == BACKEND_MISTRAL:
            bkw["mistral_api_key"] = st.text_input("API Key", type="password")
            bkw["mistral_model"]   = st.selectbox(
                "Model", ["codestral-latest","mistral-large-latest","mistral-medium-latest",
                          "mistral-small-latest","open-mixtral-8x22b"])
            model_name = bkw["mistral_model"]

        elif backend_type == BACKEND_ANTHROPIC:
            bkw["anthropic_api_key"] = st.text_input("API Key", type="password")
            bkw["anthropic_model"]   = st.selectbox(
                "Model", ["claude-sonnet-4-20250514","claude-3-5-sonnet-20241022",
                          "claude-3-opus-20240229","claude-3-haiku-20240307"])
            model_name = bkw["anthropic_model"]

        elif backend_type == BACKEND_CUSTOM:
            bkw["custom_url"]     = st.text_input("Endpoint URL")
            bkw["custom_api_key"] = st.text_input("API Key (optional)", type="password")
            bkw["custom_model"]   = st.text_input("Model ID")
            model_name = bkw.get("custom_model", "")

        bkw["temperature"] = 0.2
        auto_params = auto_chunk_params(backend_type, model_name)

        # ── Chunking ─────────────────────────────────────────────────────────
        st.markdown("**⚙ Document Chunking**")
        chunk_mode = st.radio("Mode", ["🤖 Auto (Intelligent)", "✏ Manual"],
                              horizontal=True, label_visibility="collapsed")

        if chunk_mode == "🤖 Auto (Intelligent)":
            final_params = auto_params
            bkw["max_tokens"] = auto_params["max_tokens"]
            st.markdown(f'<div class="auto-badge">⚙ {auto_params["label"]}</div>',
                        unsafe_allow_html=True)
        else:
            cs = st.slider("Chunk Size (chars)", 200, 2000, auto_params["chunk_size"], 50)
            ov = st.slider("Overlap (chars)",    0,   400, auto_params["overlap"],     25)
            mt = st.select_slider("Max Response Tokens", [512,1024,2048,3072,4096],
                                  value=auto_params["max_tokens"])
            final_params = {"chunk_size": cs, "overlap": ov, "max_tokens": mt}
            bkw["max_tokens"] = mt

        st.session_state.backend_kwargs = bkw
        st.session_state.auto_params    = final_params

        # ── Load Button ──────────────────────────────────────────────────────
        if uploaded_files:
            if st.button("Load Documents", use_container_width=True, type="primary"):
                with st.spinner(f"Loading {len(uploaded_files)} file(s)…"):
                    docs   = batch_load_documents(uploaded_files)
                    chunks = chunk_all_documents(docs, final_params["chunk_size"],
                                                 final_params["overlap"])
                st.session_state.update(
                    documents=docs, chunks=chunks,
                    findings=[], score_summary={}, search_results=[],
                    freq_data={}, analysis_done=False,
                )
                loaded = [d for d in docs if not d.get("error")]
                failed = [d for d in docs if  d.get("error")]
                st.success(f"✓ {len(loaded)} doc(s) · {len(chunks)} chunks")
                for f in failed:
                    st.error(f"✗ {f['filename']}: {f['error']}")

        st.divider()
        st.markdown("**Project / Matter**")
        st.session_state.company_name = st.text_input(
            "Company", value=st.session_state.get("company_name", ""),
            placeholder="e.g. Acme Corp — Series B", label_visibility="collapsed",
        )

        if st.button("🔌 Test Connection", use_container_width=True):
            with st.spinner("Testing…"):
                ok = LLMBackend(**bkw).test_connection()
            st.success("✓ Connected") if ok else st.error("Connection failed")
