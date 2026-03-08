"""UI Styles — all CSS injected once at startup."""
import streamlit as st


def inject_styles():
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&family=Roboto+Mono:wght@400;500&display=swap');

html,body,[class*="css"],.stApp,.stMarkdown,.stText,
button,input,select,textarea{font-family:'Roboto',sans-serif!important}
code,pre{font-family:'Roboto Mono',monospace!important}

section[data-testid="stSidebar"]{border-right:3px solid #3B82F6}

/* ── Logo ── */
.da-logo{display:flex;align-items:center;gap:10px;padding:6px 0 18px;
         border-bottom:1px solid rgba(59,130,246,.25);margin-bottom:18px}
.da-logo-icon{width:38px;height:38px;background:linear-gradient(135deg,#3B82F6,#0EA5E9);
              border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:20px}
.da-logo h2{font-size:14px;font-weight:700;margin:0;line-height:1.2}
.da-logo small{font-size:9px;opacity:.5;text-transform:uppercase;letter-spacing:1.5px}

/* ── Header ── */
.da-title{margin-bottom:28px;padding-bottom:16px;border-bottom:2px solid #3B82F6}
.da-title h1{font-size:30px;font-weight:700;margin:0 0 4px;letter-spacing:-.5px}
.da-title h1 em{font-style:normal;color:#3B82F6}
.da-title p{margin:0;font-size:13px;opacity:.5;font-weight:300}

/* ── Section label ── */
.da-sec{font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:2px;
        color:#3B82F6;margin-bottom:14px;display:flex;align-items:center;gap:8px}
.da-sec::after{content:'';flex:1;height:1px;background:rgba(59,130,246,.2)}

/* ── Badges ── */
.badge{display:inline-block;padding:2px 9px;border-radius:12px;font-size:11px;font-weight:600;letter-spacing:.5px}
.badge-HIGH  {background:#FEE2E2;color:#B91C1C;border:1px solid #FECACA}
.badge-MEDIUM{background:#FEF3C7;color:#92400E;border:1px solid #FDE68A}
.badge-LOW   {background:#DCFCE7;color:#166534;border:1px solid #BBF7D0}

/* ── Metric card ── */
.mc{border-radius:10px;border:1px solid rgba(0,0,0,.08);padding:16px;text-align:center}
.mc-v{font-size:36px;font-weight:700;line-height:1;margin-bottom:4px}
.mc-l{font-size:11px;text-transform:uppercase;letter-spacing:1.5px;opacity:.5}
.mc-HIGH   .mc-v{color:#EF4444}
.mc-MEDIUM .mc-v{color:#F59E0B}
.mc-LOW    .mc-v{color:#22C55E}
.mc-blue   .mc-v{color:#3B82F6}

/* ── Finding card ── */
.fc{border-radius:10px;border:1px solid rgba(0,0,0,.08);padding:16px 18px;
    margin-bottom:12px;border-left:4px solid #94A3B8;background:rgba(59,130,246,.03)}
.fc-HIGH  {border-left-color:#EF4444}
.fc-MEDIUM{border-left-color:#F59E0B}
.fc-LOW   {border-left-color:#22C55E}
.fc-hdr{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:10px}
.fc-cat{font-weight:600;font-size:13px}
.fc-src{font-size:11px;opacity:.5;font-family:'Roboto Mono',monospace;
        background:rgba(0,0,0,.05);padding:1px 6px;border-radius:4px}
.fc-ln{font-size:11px;color:#3B82F6;font-family:'Roboto Mono',monospace}
.fc-find{font-size:13px;font-weight:500;margin-bottom:8px;line-height:1.5}
.fc-quote{font-family:'Roboto Mono',monospace;font-size:12px;
          background:rgba(59,130,246,.07);border-left:3px solid #3B82F6;
          padding:8px 12px;margin:8px 0;border-radius:0 6px 6px 0;
          word-break:break-word;line-height:1.6}
.fc-interp{font-size:13px;line-height:1.65;opacity:.75}
.fc-qlbl{font-size:10px;font-weight:600;text-transform:uppercase;
         letter-spacing:1.5px;color:#3B82F6;margin:10px 0 6px}
.fc-qi{font-size:12px;line-height:1.6;opacity:.7;padding:3px 0 3px 14px;position:relative}
.fc-qi::before{content:'→';position:absolute;left:0;color:#3B82F6}

/* ── Filter bar ── */
.filter-bar{display:flex;gap:8px;flex-wrap:wrap;padding:10px 14px;
            background:rgba(59,130,246,.04);border-radius:8px;
            border:1px solid rgba(59,130,246,.12);margin-bottom:16px}
.fbtn{padding:5px 12px;border-radius:16px;font-size:12px;font-weight:600;
      cursor:pointer;border:1px solid transparent;letter-spacing:.3px}
.fbtn-active{background:#3B82F6;color:white;border-color:#3B82F6}
.fbtn-inactive{background:rgba(0,0,0,.04);color:#64748B;border-color:rgba(0,0,0,.1)}

/* ── Search results ── */
.sr{border-radius:8px;padding:0;margin-bottom:14px;border:1px solid rgba(0,0,0,.08);overflow:hidden}
.sr-hdr{background:rgba(59,130,246,.06);padding:10px 14px;
        border-bottom:1px solid rgba(59,130,246,.12);display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.sr-doc{font-weight:700;font-size:13px}
.sr-ln{font-size:11px;font-family:'Roboto Mono',monospace;color:#0EA5E9;
       background:rgba(14,165,233,.1);padding:2px 7px;border-radius:10px}
.sr-cnt{font-size:11px;background:rgba(0,0,0,.06);padding:2px 7px;border-radius:10px}
.sr-kw{font-size:11px;background:rgba(245,158,11,.15);color:#92400E;
       padding:2px 7px;border-radius:10px;border:1px solid rgba(245,158,11,.25)}
.sr-body{padding:12px 14px}
.sr-match{margin-bottom:10px;border-left:2px solid #E2E8F0;padding-left:12px}
.sr-match:last-child{margin-bottom:0}
.sr-match-kw{font-size:10px;font-weight:600;text-transform:uppercase;
             letter-spacing:1px;color:#64748B;margin-bottom:4px}
.sr-ctx{font-size:13px;line-height:1.75;word-break:break-word}
.sr-ctx mark{background:#FEF08A;color:#713F12;border-radius:2px;padding:0 2px;font-weight:600}

/* ── LLM Query bubbles ── */
.q-bub{padding:12px 16px;border-radius:8px;background:rgba(59,130,246,.07);
       border-left:3px solid #3B82F6;font-size:14px;font-weight:500;margin-bottom:10px}
.a-bub{padding:16px 20px;border-radius:8px;border:1px solid rgba(0,0,0,.08);
       background:rgba(20,184,166,.04);border-left:3px solid #14B8A6;
       font-size:13px;line-height:1.75}
.a-lbl{font-size:10px;text-transform:uppercase;letter-spacing:1.5px;
       font-weight:600;color:#14B8A6;margin-bottom:8px}

/* ── Document viewer ── */
.doc-viewer{background:rgba(0,0,0,.02);border:1px solid rgba(0,0,0,.07);
            border-radius:8px;padding:16px 20px;font-size:13px;line-height:1.85;
            white-space:pre-wrap;word-break:break-word;
            font-family:'Roboto Mono',monospace;max-height:70vh;overflow-y:auto}
.dv-line{display:block;padding:1px 0}
.dv-line:hover{background:rgba(59,130,246,.05)}
.dv-ln{color:#3B82F6;user-select:none;margin-right:16px;min-width:46px;
       display:inline-block;text-align:right;font-size:11px;opacity:.7}
.dv-hl-HIGH  {background:rgba(239,68,68,.12);border-left:3px solid #EF4444;
              padding-left:4px;margin-left:-7px}
.dv-hl-MEDIUM{background:rgba(245,158,11,.12);border-left:3px solid #F59E0B;
              padding-left:4px;margin-left:-7px}
.dv-hl-LOW   {background:rgba(34,197,94,.1);border-left:3px solid #22C55E;
              padding-left:4px;margin-left:-7px}

/* ── Page navigation ── */
.page-nav{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px;padding:8px 12px;
          background:rgba(59,130,246,.04);border-radius:8px;
          border:1px solid rgba(59,130,246,.1)}
.page-pill{display:inline-block;padding:3px 10px;border-radius:12px;font-size:11px;
           font-weight:600;cursor:pointer;border:1px solid rgba(59,130,246,.3);
           color:#3B82F6;background:white}
.page-pill-active{background:#3B82F6;color:white;border-color:#3B82F6}
.page-pill-flagged{border-color:#EF4444;color:#EF4444}

/* ── Table viewer ── */
.tbl-marker-start{background:rgba(16,185,129,.1);border-left:4px solid #10B981;
                  padding:5px 12px;margin:10px 0 4px;border-radius:0 4px 4px 0;
                  font-size:12px;font-weight:600;color:#065F46}
.tbl-marker-end{background:rgba(0,0,0,.03);border-left:4px solid #94A3B8;
                padding:3px 12px;margin:2px 0 12px;border-radius:0 4px 4px 0;
                font-size:11px;color:#64748B}

/* ── Findings sidebar pills ── */
.fpin{display:inline-block;padding:2px 8px;border-radius:10px;font-size:10px;
      font-weight:600;margin:1px;cursor:default}
.fpin-HIGH  {background:#FEE2E2;color:#991B1B}
.fpin-MEDIUM{background:#FEF3C7;color:#92400E}
.fpin-LOW   {background:#DCFCE7;color:#166534}

/* ── Misc ── */
.dp{display:inline-flex;align-items:center;gap:5px;font-size:12px;
    padding:3px 10px;border-radius:14px;background:rgba(59,130,246,.08);
    border:1px solid rgba(59,130,246,.2);margin:2px}
.info-strip{padding:10px 14px;border-radius:8px;font-size:13px;
            background:rgba(59,130,246,.06);border:1px solid rgba(59,130,246,.15);
            margin-bottom:16px;line-height:1.6}
.auto-badge{display:inline-flex;align-items:center;gap:6px;padding:6px 12px;
            border-radius:6px;font-size:12px;background:rgba(20,184,166,.1);
            border:1px solid rgba(20,184,166,.25);color:#0D9488}
.empty-state{text-align:center;padding:56px 24px;opacity:.5}
.empty-state .es-icon{font-size:48px;margin-bottom:14px}
.empty-state h3{font-size:18px;font-weight:600;margin-bottom:8px}
.empty-state p{font-size:13px;line-height:1.6;max-width:360px;margin:0 auto}
.da-footer{margin-top:48px;padding-top:16px;text-align:center;
           border-top:1px solid rgba(0,0,0,.08);font-size:12px;opacity:.4}
</style>
""", unsafe_allow_html=True)
