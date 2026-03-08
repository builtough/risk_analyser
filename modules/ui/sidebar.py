"""Sidebar — file upload, backend config, chunking, load button, admin trigger."""
import streamlit as st
from modules.document_handler import batch_load_documents
from modules.chunker import chunk_all_documents, auto_chunk_params
from modules.llm_backend import (LLMBackend, BACKEND_LIST, BACKEND_MODELS,
                                  BACKEND_OLLAMA, BACKEND_MISTRAL,
                                  BACKEND_ANTHROPIC, BACKEND_CUSTOM,
                                  default_model)
from modules.ui.admin import render_admin_trigger, get_locked_backend_kwargs
from modules.table_extractor import batch_extract_tables, tables_to_chunks


def render_sidebar():
    with st.sidebar:
        # ── Logo / Branding ───────────────────────────────────────────────────
        st.markdown("""
        <div class="da-logo">
            <div class="da-logo-icon">🔬</div>
            <div>
                <h2>APEX</h2>
            </div>
        </div>""", unsafe_allow_html=True)

        # ── File Upload ───────────────────────────────────────────────────────
        st.markdown("**📂 Upload Documents**")
        uploaded_files = st.file_uploader(
            "PDF · Word · Excel",
            type=["pdf", "docx", "doc", "xlsx", "xls"],
            accept_multiple_files=True,
            label_visibility="collapsed",
        )

        # ── AI Backend ────────────────────────────────────────────────────────
        llm_restricted = st.session_state.get("llm_restricted", False)
        model_name = ""

        if llm_restricted:
            bkw = get_locked_backend_kwargs()
            st.session_state.backend_kwargs = bkw
            model_name = st.session_state.get("llm_locked_model", "")
            st.markdown(
                f'<div style="font-size:11px;color:#64748B;padding:5px 8px;'
                f'background:rgba(0,0,0,0.06);border-radius:5px;margin-bottom:6px;">'
                f'🤖 {st.session_state.get("llm_locked_backend","")} · '
                f'<code style="font-size:10px;">{model_name}</code></div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown("**🤖 AI Backend**")
            backend_type = st.selectbox(
                "Backend", BACKEND_LIST, label_visibility="collapsed",
            )
            bkw = {"backend_type": backend_type}

            if backend_type == BACKEND_OLLAMA:
                # ollama_url_default = "http://host.docker.internal:11434"  # docker variant
                bkw["ollama_url"]   = st.text_input("Ollama URL", "http://localhost:11434")
                bkw["ollama_model"] = st.selectbox("Model", BACKEND_MODELS[BACKEND_OLLAMA])
                model_name = bkw["ollama_model"]

            elif backend_type == BACKEND_MISTRAL:
                bkw["mistral_api_key"] = st.text_input("API Key", type="password")
                bkw["mistral_model"]   = st.selectbox("Model", BACKEND_MODELS[BACKEND_MISTRAL])
                model_name = bkw["mistral_model"]

            elif backend_type == BACKEND_ANTHROPIC:
                bkw["anthropic_api_key"] = st.text_input("API Key", type="password")
                bkw["anthropic_model"]   = st.selectbox("Model", BACKEND_MODELS[BACKEND_ANTHROPIC])
                model_name = bkw["anthropic_model"]

            elif backend_type == BACKEND_CUSTOM:
                bkw["custom_url"]     = st.text_input("Endpoint URL")
                bkw["custom_api_key"] = st.text_input("API Key (optional)", type="password")
                bkw["custom_model"]   = st.text_input("Model ID")
                model_name = bkw.get("custom_model", "")

            # temperature: float = 0.1   # more deterministic for small models
            bkw["temperature"] = 0.2
            st.session_state.backend_kwargs = bkw

        # ── Chunking ──────────────────────────────────────────────────────────
        backend_for_params = (
            st.session_state.get("llm_locked_backend", "")
            if llm_restricted
            else st.session_state.backend_kwargs.get("backend_type", "")
        )
        auto_params = auto_chunk_params(backend_for_params, model_name)

        st.markdown("**⚙ Document Chunking**")
        # chunk_mode_default = "✏ Manual"   # uncomment to default to manual mode
        chunk_mode = st.radio(
            "Mode", ["🤖 Auto (Intelligent)", "✏ Manual"],
            horizontal=True, label_visibility="collapsed",
        )

        if chunk_mode == "🤖 Auto (Intelligent)":
            final_params = auto_params
            st.session_state.backend_kwargs["max_tokens"] = auto_params["max_tokens"]
            st.markdown(f'<div class="auto-badge">⚙ {auto_params["label"]}</div>',
                        unsafe_allow_html=True)
        else:
            cs = st.slider("Chunk Size (chars)", 200, 2000, auto_params["chunk_size"], 50)
            ov = st.slider("Overlap (chars)",      0,  400, auto_params["overlap"],     25)
            mt = st.select_slider("Max Response Tokens", [512, 1024, 2048, 3072, 4096],
                                  value=auto_params["max_tokens"])
            final_params = {"chunk_size": cs, "overlap": ov, "max_tokens": mt}
            st.session_state.backend_kwargs["max_tokens"] = mt

        st.session_state.auto_params = final_params

        # ── Load Button ───────────────────────────────────────────────────────
        if uploaded_files:
            if st.button("Load Documents", use_container_width=True, type="primary"):
                with st.spinner(f"Loading {len(uploaded_files)} file(s)…"):
                    docs   = batch_load_documents(uploaded_files)
                    chunks = chunk_all_documents(
                        docs, final_params["chunk_size"], final_params["overlap"]
                    )
                with st.spinner("Extracting tables…"):
                    tables       = batch_extract_tables(uploaded_files)
                    table_chunks = tables_to_chunks(tables)
                    all_chunks   = chunks + table_chunks

                st.session_state.update(
                    documents=docs,
                    chunks=all_chunks,
                    findings=[],
                    score_summary={},
                    search_results=[],
                    freq_data={},
                    analysis_done=False,
                    extracted_tables=tables,
                    example_questions=None,   # reset so new questions are generated
                )
                # Build BM25 index for retrieval
                from modules.search import build_bm25_index
                build_bm25_index(all_chunks)

                loaded = [d for d in docs if not d.get("error")]
                failed = [d for d in docs if  d.get("error")]
                n_tables = len(tables)
                table_note = f" · {n_tables} table(s)" if n_tables else ""
                st.success(f"✓ {len(loaded)} doc(s) · {len(all_chunks)} chunks{table_note}")
                for f in failed:
                    st.error(f"✗ {f['filename']}: {f['error']}")

        # ── Project / Matter ──────────────────────────────────────────────────
        st.divider()
        st.markdown("**Project / Matter**")
        st.session_state.company_name = st.text_input(
            "Company",
            value=st.session_state.get("company_name", ""),
            placeholder="e.g. Acme Corp — Series B",
            label_visibility="collapsed",
        )

        # ── Test Connection ───────────────────────────────────────────────────
        if st.button("🔌 Test Connection", use_container_width=True):
            with st.spinner("Testing…"):
                ok = LLMBackend(**st.session_state.backend_kwargs).test_connection()
            (st.success if ok else st.error)("✓ Connected" if ok else "Connection failed")

        # ── Admin trigger ─────────────────────────────────────────────────────
        st.divider()
        render_admin_trigger()
