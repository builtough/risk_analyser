"""
Admin Panel — Login, Tab Visibility & LLM Backend Restriction
Trigger: small ⚙ button at the bottom of the sidebar.
"""
import hashlib
import streamlit as st
from modules.llm_backend import (BACKEND_LIST, BACKEND_MODELS, BACKEND_OLLAMA,
                                  BACKEND_CUSTOM, default_model)

# ── Credentials ───────────────────────────────────────────────────────────────
# To change password: hashlib.sha256("newpassword".encode()).hexdigest()
_CREDENTIALS = {
    st.secrets["ada"]["a"]: st.secrets["ada"]["b"],  # 
}

# ── Tab registry ──────────────────────────────────────────────────────────────

ALL_TABS = [
    {"key": "analysis",  "label": "⚖ Risk Analysis",    "default": False,  "admin_only": False},
    {"key": "search",    "label": "🔍 Document Search",  "default": True,  "admin_only": False},
    {"key": "query",     "label": "💬 LLM Query",         "default": True,  "admin_only": False},
    {"key": "viewer",    "label": "📄 Document Viewer",   "default": True,  "admin_only": False},
    {"key": "dashboard", "label": "📊 Analytics",         "default": False,  "admin_only": False},
    {"key": "reports",   "label": "📑 Export Reports",    "default": False,  "admin_only": False},
    {"key": "tables",    "label": "📋 Tables",            "default": True,  "admin_only": False},
    {"key": "debug",     "label": "🛠 Debug",             "default": False, "admin_only": True},
]

# ── Public: called once at startup by app.py ──────────────────────────────────

def init_admin_state():
    """Initialise session state for admin flags."""
    defaults = {
        "tab_visibility":         None,      # filled below
        "admin_logged_in":        False,
        "admin_login_error":      "",
        "show_admin_panel":       False,
        "llm_restricted":         False,
        "llm_locked_backend":     BACKEND_OLLAMA,
        "llm_locked_model":       default_model(BACKEND_OLLAMA),
        "llm_locked_url":         "http://localhost:11434",
        "llm_locked_api_key":     "",
        "llm_locked_custom_url":  "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # Initialise / backfill tab_visibility
    if st.session_state.tab_visibility is None:
        st.session_state.tab_visibility = {
            t["key"]: (t["default"] and not t["admin_only"])
            for t in ALL_TABS
        }
    else:
        for t in ALL_TABS:
            if t["key"] not in st.session_state.tab_visibility:
                st.session_state.tab_visibility[t["key"]] = (
                    t["default"] and not t["admin_only"]
                )


def get_visible_tabs():
    init_admin_state()
    return [t for t in ALL_TABS
            if st.session_state.tab_visibility.get(t["key"], False)]


def get_locked_backend_kwargs() -> dict:
    backend = st.session_state.llm_locked_backend
    # temperature: float = 0.1   # lower for more deterministic local model output
    bkw = {"backend_type": backend, "temperature": 0.2, "max_tokens": 2048}
    if backend == "Ollama (Local)":
        bkw["ollama_url"]   = st.session_state.llm_locked_url
        bkw["ollama_model"] = st.session_state.llm_locked_model
    elif backend == "Mistral AI":
        bkw["mistral_api_key"] = st.session_state.llm_locked_api_key
        bkw["mistral_model"]   = st.session_state.llm_locked_model
    elif backend == "Anthropic (Claude)":
        bkw["anthropic_api_key"] = st.session_state.llm_locked_api_key
        bkw["anthropic_model"]   = st.session_state.llm_locked_model
    elif backend == "Custom Endpoint":
        bkw["custom_url"]     = st.session_state.llm_locked_custom_url
        bkw["custom_api_key"] = st.session_state.llm_locked_api_key
        bkw["custom_model"]   = st.session_state.llm_locked_model
    return bkw


def _check_password(username: str, password: str) -> bool:
    stored = _CREDENTIALS.get(username.strip().lower())
    if not stored:
        return False
    return hashlib.sha256(password.encode()).hexdigest() == stored


# ── Sidebar trigger button ────────────────────────────────────────────────────

def render_admin_trigger():
    st.markdown("""
        <style>
        .admin-trigger-wrap button {
            background: transparent !important;
            border: 1px solid rgba(100,116,139,0.25) !important;
            color: #64748B !important;
            font-size: 10px !important;
            padding: 1px 10px !important;
            border-radius: 4px !important;
            min-height: 24px !important;
            height: 24px !important;
            line-height: 1 !important;
            box-shadow: none !important;
        }
        .admin-trigger-wrap button:hover {
            border-color: rgba(59,130,246,0.5) !important;
            color: #3B82F6 !important;
        }
        </style>
    """, unsafe_allow_html=True)

    label = "🔓 admin" if st.session_state.admin_logged_in else "⚙"
    st.markdown('<div class="admin-trigger-wrap">', unsafe_allow_html=True)
    if st.button(label, key="admin_trigger_btn"):
        st.session_state.show_admin_panel = not st.session_state.show_admin_panel
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


# ── Admin panel ───────────────────────────────────────────────────────────────

def render_admin_panel():
    st.markdown("""
        <div style="border:1px solid rgba(59,130,246,0.3);border-radius:12px;
                    padding:24px 28px 20px;
                    background:linear-gradient(135deg,#0F172A 0%,#1E3A5F 100%);
                    margin-bottom:20px;">
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px;">
            <span style="font-size:20px;">⚙</span>
            <span style="font-size:17px;font-weight:700;color:#F8FAFC;">Admin Panel</span>
            <span style="font-size:11px;color:#475569;margin-left:auto;">
              Document Intelligence Platform · System Configuration
            </span>
          </div>
          <div style="height:1px;background:rgba(59,130,246,0.25);margin:10px 0 14px;"></div>
    """, unsafe_allow_html=True)

    if not st.session_state.admin_logged_in:
        _render_login()
    else:
        _render_controls()

    st.markdown("</div>", unsafe_allow_html=True)

    if st.button("✕  Close", key="close_admin_panel"):
        st.session_state.show_admin_panel = False
        st.rerun()
    st.divider()


def _render_login():
    st.markdown(
        '<p style="color:#94A3B8;font-size:13px;margin-bottom:14px;">'
        "Enter administrator credentials.</p>",
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        username = st.text_input("u", placeholder="Username",
                                  label_visibility="collapsed", key="admin_u")
    with c2:
        password = st.text_input("p", placeholder="Password", type="password",
                                  label_visibility="collapsed", key="admin_p")
    with c3:
        clicked = st.button("Login", type="primary",
                             use_container_width=True, key="admin_login_btn")

    if clicked:
        if _check_password(username, password):
            st.session_state.admin_logged_in   = True
            st.session_state.admin_login_error = ""
            st.rerun()
        else:
            st.session_state.admin_login_error = "Invalid credentials."

    if st.session_state.admin_login_error:
        st.error(st.session_state.admin_login_error)


def _render_controls():
    st.markdown(
        '<p style="color:#94A3B8;font-size:12px;margin-bottom:14px;">'
        "Logged in as <strong style='color:#3B82F6'>admin</strong>. "
        "Changes apply immediately.</p>",
        unsafe_allow_html=True,
    )

    left, right = st.columns(2, gap="large")

    with left:
        st.markdown(
            '<p style="color:#94A3B8;font-size:11px;font-weight:600;'
            'text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;">'
            '📑 Tab Visibility</p>',
            unsafe_allow_html=True,
        )
        for tab in ALL_TABS:
            k     = tab["key"]
            is_on = st.session_state.tab_visibility.get(k, False)
            tag   = " 🔒" if tab["admin_only"] else ""
            new_v = st.toggle(f"{tab['label']}{tag}", value=is_on, key=f"ttog_{k}")
            if new_v != is_on:
                st.session_state.tab_visibility[k] = new_v
                st.rerun()

        qa, qb = st.columns(2)
        with qa:
            if st.button("All On", use_container_width=True, key="tabs_allon"):
                for t in ALL_TABS:
                    st.session_state.tab_visibility[t["key"]] = True
                st.rerun()
        with qb:
            if st.button("Reset", use_container_width=True, key="tabs_reset"):
                st.session_state.tab_visibility = {
                    t["key"]: t["default"] and not t["admin_only"]
                    for t in ALL_TABS
                }
                st.rerun()
        n = sum(st.session_state.tab_visibility.values())
        st.caption(f"{n} of {len(ALL_TABS)} tabs visible")

    with right:
        st.markdown(
            '<p style="color:#94A3B8;font-size:11px;font-weight:600;'
            'text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;">'
            '🤖 LLM Backend Lock</p>',
            unsafe_allow_html=True,
        )

        restricted = st.toggle(
            "Lock users to a specific backend",
            value=st.session_state.llm_restricted,
            key="llm_restrict_toggle",
        )
        if restricted != st.session_state.llm_restricted:
            st.session_state.llm_restricted = restricted
            if restricted:
                st.session_state.backend_kwargs = get_locked_backend_kwargs()
            st.rerun()

        if restricted:
            st.caption("⚠ AI Backend section hidden from users.")
            backend_list = BACKEND_LIST
            cur_b = st.session_state.llm_locked_backend
            new_b = st.selectbox(
                "Backend", backend_list,
                index=backend_list.index(cur_b) if cur_b in backend_list else 0,
                key="locked_backend_sel",
            )
            if new_b != cur_b:
                st.session_state.llm_locked_backend = new_b
                st.session_state.llm_locked_model   = default_model(new_b)
                st.rerun()

            models = BACKEND_MODELS.get(new_b, [])
            if new_b == "Custom Endpoint":
                st.session_state.llm_locked_model      = st.text_input(
                    "Model ID", value=st.session_state.llm_locked_model, key="locked_model_txt")
                st.session_state.llm_locked_custom_url = st.text_input(
                    "Endpoint URL", value=st.session_state.llm_locked_custom_url, key="locked_cust_url")
                st.session_state.llm_locked_api_key    = st.text_input(
                    "API Key (optional)", value=st.session_state.llm_locked_api_key,
                    type="password", key="locked_api_key")
            elif new_b == "Ollama (Local)":
                cur_m = st.session_state.llm_locked_model
                st.session_state.llm_locked_model = st.selectbox(
                    "Model", models,
                    index=models.index(cur_m) if cur_m in models else 0, key="locked_model_sel")
                st.session_state.llm_locked_url   = st.text_input(
                    "Ollama URL", value=st.session_state.llm_locked_url, key="locked_ollama_url")
            else:
                cur_m = st.session_state.llm_locked_model
                st.session_state.llm_locked_model  = st.selectbox(
                    "Model", models,
                    index=models.index(cur_m) if cur_m in models else 0, key="locked_model_sel")
                st.session_state.llm_locked_api_key = st.text_input(
                    "API Key", value=st.session_state.llm_locked_api_key,
                    type="password", key="locked_api_key")

            if st.button("✓ Apply & Lock", type="primary",
                         use_container_width=True, key="apply_lock"):
                st.session_state.backend_kwargs = get_locked_backend_kwargs()
                st.success(f"Locked · {st.session_state.llm_locked_backend} "
                           f"· {st.session_state.llm_locked_model}")
                st.rerun()

            b = st.session_state.llm_locked_backend
            m = st.session_state.llm_locked_model
            st.markdown(
                f'<div style="margin-top:8px;padding:6px 10px;border-radius:6px;'
                f'background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.3);">'
                f'<span style="font-size:11px;color:#FCA5A5;">🔒 {b} · <code'
                f' style="color:#FCA5A5;">{m}</code></span></div>',
                unsafe_allow_html=True,
            )
        else:
            st.caption("Users can freely choose any backend from the sidebar.")

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔓 Logout", key="admin_logout"):
        st.session_state.admin_logged_in   = False
        st.session_state.admin_login_error = ""
        st.rerun()
