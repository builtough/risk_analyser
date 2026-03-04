"""Reports & Export Tab — PDF, Excel, JSON download."""
import json
import streamlit as st
from datetime import datetime

from modules.reporter import generate_pdf_report, generate_excel_report
from modules.ui.helpers import clean, metric_card, badge


def render_tab_reports():
    st.markdown('<div class="da-sec">📑 Export & Compliance Reports</div>',
                unsafe_allow_html=True)

    if not st.session_state.get("analysis_done"):
        st.markdown(
            '<div class="empty-state"><div class="es-icon">📑</div>'
            '<h3>No Analysis to Export</h3>'
            '<p>Complete a Risk Analysis first to generate reports.</p></div>',
            unsafe_allow_html=True)
        return

    findings = st.session_state.findings
    summ     = st.session_state.score_summary
    company  = st.session_state.get("company_name") or "Confidential"
    ov       = summ.get("overall_risk", "LOW")

    # Summary metrics
    rs1, rs2, rs3, rs4, rs5 = st.columns(5)
    for col, val, lbl, cls in [
        (rs1, ov,                 "Overall",  f"mc-{ov}"),
        (rs2, summ.get("total",0),"Total",    "mc-blue"),
        (rs3, summ.get("high", 0),"High",     "mc-HIGH"),
        (rs4, summ.get("medium",0),"Medium",  "mc-MEDIUM"),
        (rs5, summ.get("low",  0),"Low",      "mc-LOW"),
    ]:
        with col:
            st.markdown(metric_card(val, lbl, cls), unsafe_allow_html=True)
    st.markdown("---")

    # Findings preview
    st.markdown("#### Findings Preview")
    for i, f in enumerate(findings, 1):
        risk  = f.get("risk_level", "LOW")
        cat   = clean(f.get("category_label",""))
        fname = f.get("filename","")
        sl, el= f.get("start_line","?"), f.get("end_line","?")
        with st.expander(f"#{i} · {risk} · {cat} · {fname} · Lines {sl}–{el}"):
            c1, c2 = st.columns([1, 3])
            with c1:
                st.markdown(
                    f"**Risk:** {risk}  \n**File:** {fname}  \n"
                    f"**Lines:** {sl}–{el}  \n**Category:** {cat}")
            with c2:
                st.markdown(f"**Finding:**  \n{clean(f.get('finding',''))}")
                prob = clean(f.get("problematic_language",""))
                if prob and prob.upper() not in ("N/A",""):
                    st.markdown("**Flagged Language:**")
                    st.code(prob, language=None)
                st.markdown(f"**Interpretation:**  \n{clean(f.get('interpretation',''))}")
                qs = [clean(q) for q in f.get("follow_up_questions",[]) if q]
                if qs:
                    st.markdown("**Follow-up Questions:**")
                    for q in qs:
                        st.markdown(f"→ {q}")

    st.markdown("---")

    # Export buttons
    ec1, ec2 = st.columns(2)

    with ec1:
        st.markdown("#### 📄 PDF Report")
        st.caption("Executive summary, all findings, risk scoring, follow-up questions.")
        if st.button("Generate PDF", use_container_width=True):
            try:
                with st.spinner("Building PDF…"):
                    pdf = generate_pdf_report(findings, summ, company)
                st.download_button(
                    "⬇ Download PDF", data=pdf,
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
                st.download_button(
                    "⬇ Download Excel", data=xlsx,
                    file_name=f"contract_risk_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True)
            except Exception as e:
                st.error(f"Excel error: {e}")

    with st.expander("🔧 Raw JSON Export"):
        json_out = json.dumps({
            "generated_at": datetime.now().isoformat(),
            "company":      company,
            "summary":      summ,
            "findings": [
                {k: clean(v) if isinstance(v, str) else v for k, v in f.items()}
                for f in findings
            ],
        }, indent=2)
        st.code(json_out, language="json")
        st.download_button(
            "⬇ Download JSON", data=json_out,
            file_name=f"findings_{datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json")
