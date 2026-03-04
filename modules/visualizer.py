"""
Visualizer Module — fixed colorbar titlefont bug, added text statistics chart.
"""
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from typing import Dict, List, Any

# ── Theme ──────────────────────────────────────────────────────────────────────
C = {
    "high": "#EF4444", "medium": "#F59E0B", "low": "#22C55E",
    "blue": "#3B82F6", "teal": "#14B8A6", "purple": "#8B5CF6",
    "text": "#1E293B", "subtext": "#64748B", "bg": "rgba(0,0,0,0)"
}
LAYOUT = dict(paper_bgcolor=C["bg"], plot_bgcolor=C["bg"],
              font=dict(family="Roboto, sans-serif", color=C["text"]),
              margin=dict(l=16, r=16, t=44, b=16))


def plot_keyword_frequency(freq_data: Dict[str, Dict[str, int]]) -> go.Figure:
    if not freq_data:
        return _empty("No keyword data available")
    rows = [{"Document": f, "Keyword": k, "Count": v}
            for f, kd in freq_data.items() for k, v in kd.items() if v > 0]
    if not rows:
        return _empty("No keyword matches found")
    df = pd.DataFrame(rows)
    fig = px.bar(df, x="Keyword", y="Count", color="Document", barmode="group",
                 color_discrete_sequence=px.colors.qualitative.Safe,
                 title="Keyword Frequency by Document")
    fig.update_layout(**LAYOUT,
                      xaxis=dict(tickangle=-30, gridcolor="rgba(0,0,0,0.06)"),
                      yaxis=dict(gridcolor="rgba(0,0,0,0.06)"),
                      title_font_size=15)
    return fig


def plot_risk_distribution(score_summary: Dict) -> go.Figure:
    h, m, l = score_summary.get("high",0), score_summary.get("medium",0), score_summary.get("low",0)
    if h + m + l == 0:
        return _empty("No risk findings to visualize")
    fig = go.Figure(go.Pie(
        labels=["High Risk","Medium Risk","Low Risk"], values=[h, m, l], hole=0.52,
        marker=dict(colors=[C["high"], C["medium"], C["low"]],
                    line=dict(color="white", width=2)),
        textinfo="label+percent",
        hovertemplate="<b>%{label}</b><br>Count: %{value}<br>%{percent}<extra></extra>"
    ))
    total = h + m + l
    fig.add_annotation(text=f"<b>{total}</b><br>Total", x=0.5, y=0.5,
                       showarrow=False, font=dict(size=15, color=C["text"]))
    fig.update_layout(**LAYOUT, title=dict(text="Risk Distribution", font_size=15),
                      legend=dict(orientation="h", y=-0.12))
    return fig


def plot_category_breakdown(score_summary: Dict) -> go.Figure:
    from modules.analyzer import RISK_CATEGORIES
    by_cat = score_summary.get("by_category", {})
    rows = [(RISK_CATEGORIES.get(k,{}).get("label", k), v)
            for k, v in by_cat.items() if v["total"] > 0]
    if not rows:
        return _empty("No category data")
    labels = [r[0] for r in rows]
    fig = go.Figure()
    for vals, name, color in [
        ([r[1]["HIGH"] for r in rows], "High", C["high"]),
        ([r[1]["MEDIUM"] for r in rows], "Medium", C["medium"]),
        ([r[1]["LOW"] for r in rows], "Low", C["low"]),
    ]:
        fig.add_trace(go.Bar(name=name, y=labels, x=vals, orientation='h',
                             marker_color=color,
                             hovertemplate=f"<b>{name}</b>: %{{x}}<extra></extra>"))
    fig.update_layout(**LAYOUT, barmode='stack', title=dict(text="Findings by Category", font_size=15),
                      xaxis=dict(gridcolor="rgba(0,0,0,0.06)"),
                      legend=dict(orientation="h", y=-0.18))
    return fig


def plot_keyword_heatmap(freq_data: Dict[str, Dict[str, int]]) -> go.Figure:
    if not freq_data:
        return _empty("No data for heatmap")
    docs = list(freq_data.keys())
    keywords = list(next(iter(freq_data.values())).keys()) if freq_data else []
    if not keywords:
        return _empty("No keywords to display")
    matrix = [[freq_data[doc].get(kw, 0) for doc in docs] for kw in keywords]
    doc_labels = [d[:22] + "…" if len(d) > 22 else d for d in docs]
    fig = go.Figure(go.Heatmap(
        z=matrix, x=doc_labels, y=keywords,
        colorscale=[[0,"#EFF6FF"],[0.4,"#93C5FD"],[0.75,"#2563EB"],[1,"#1E3A5F"]],
        hovertemplate="<b>%{y}</b> in <b>%{x}</b><br>Count: %{z}<extra></extra>",
        showscale=True,
        colorbar=dict(
            title=dict(text="Count", font=dict(color=C["text"], size=11)),  # ← fixed
            tickfont=dict(color=C["text"], size=10)
        )
    ))
    fig.update_layout(**LAYOUT, title=dict(text="Keyword Density Heatmap", font_size=15),
                      xaxis=dict(tickangle=-30),
                      height=max(300, len(keywords) * 38 + 100))
    return fig


def plot_document_stats(documents: List[Dict]) -> go.Figure:
    """Bar chart: word count and chunk count per document."""
    if not documents:
        return _empty("No documents loaded")
    rows = []
    for d in documents:
        if not d.get("error"):
            wc = len(d.get("raw_text","").split())
            rows.append({"Document": d["filename"][:20], "Words": wc,
                         "Pages/Sections": len(d.get("pages",[]))})
    if not rows:
        return _empty("No document stats available")
    df = pd.DataFrame(rows)
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Word Count", x=df["Document"], y=df["Words"],
                         marker_color=C["blue"], yaxis="y"))
    fig.add_trace(go.Bar(name="Pages / Sections", x=df["Document"], y=df["Pages/Sections"],
                         marker_color=C["teal"], yaxis="y2"))
    fig.update_layout(
        **LAYOUT,
        title=dict(text="Document Size Overview", font_size=15),
        yaxis=dict(title="Word Count", gridcolor="rgba(0,0,0,0.06)"),
        yaxis2=dict(title="Pages / Sections", overlaying="y", side="right"),
        barmode="group", legend=dict(orientation="h", y=-0.18)
    )
    return fig


def _empty(msg: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=msg, x=0.5, y=0.5, xref="paper", yref="paper",
                       showarrow=False, font=dict(size=13, color=C["subtext"]))
    fig.update_layout(**LAYOUT, xaxis_visible=False, yaxis_visible=False)
    return fig