"""Weekly scorecard for the support lead."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

from src import metrics as m  # noqa: E402
from src.ui import C, SERIES, get_df, inject_css, kpi_row, note, page_header, pct, section, style_fig  # noqa: E402

inject_css()
df = get_df()
weekly = m.weekly_kpis(df)
h = m.headline(df)

page_header("Lead · Weekly scorecard", "Is the backlog coming down without hurting clients?",
            "Weekly, by ticket creation week (Mon–Sun). The driver metric sits next to its guardrails: "
            "escalating less is only good if reopens, CSAT and first response hold.")

kpi_row([
    {"label": "Open backlog, 30 Sep", "value": h["backlog_30_sep"],
     "sub": f"+{h['backlog_30_sep'] - h['backlog_31_jul']} vs 31 Jul (+60%)", "tone": "bad"},
    {"label": "Escalations returned unfixed", "value": pct(h["wasted_pct"]), "sub": "driver · target < 35%",
     "tone": "accent"},
    {"label": "Reopen rate", "value": pct(h["reopen_pct"]), "sub": "guardrail"},
    {"label": "CSAT (mean)", "value": f"{h['csat_mean']:.2f}", "sub": f"guardrail · {pct(h['csat_resp_rate'])} respond"},
    {"label": "Median close, escalated", "value": f"{h['med_ttr_esc']:.0f}h",
     "sub": f"{h['med_ttr_non_esc']:.1f}h if not escalated"},
])


def line(col, title, y_title, color, is_pct=False, target=None):
    fig = go.Figure(go.Scatter(
        x=weekly["week"], y=weekly[col], mode="lines+markers", line=dict(color=color),
        marker=dict(size=8, line=dict(width=2, color=C["card"])), name=title,
        hovertemplate="Week of %{x|%d %b}: %{y" + (":.0%" if is_pct else ":.1f") + "}<extra></extra>"))
    if target is not None:
        fig.add_hline(y=target, line=dict(color=C["muted_fg"], width=1, dash="dash"),
                      annotation_text=f"target {target:.0%}", annotation_position="top left",
                      annotation_font=dict(size=11, color=C["muted_fg"]))
    fig.update_layout(title=title)
    if is_pct:
        fig.update_yaxes(tickformat=".0%", rangemode="tozero")
    return style_fig(fig, y_title)


section("Backlog and demand")
c1, c2 = st.columns(2)
c1.plotly_chart(line("backlog", "Open backlog at week end", "Open tickets", SERIES[0]), use_container_width=True)
c2.plotly_chart(line("volume", "Tickets created per week", "Tickets", SERIES[3]), use_container_width=True)

section("Driver")
st.plotly_chart(line("wasted_pct", "Escalations returned from engineering without a fix", "% of escalations",
                     SERIES[1], True, target=0.35), use_container_width=True)

section("Guardrails")
g1, g2, g3 = st.columns(3)
g1.plotly_chart(line("reopen_pct", "Reopen rate", "% of tickets", SERIES[2], True), use_container_width=True)
g2.plotly_chart(line("csat", "CSAT (mean of responses)", "CSAT (1–5)", SERIES[2]), use_container_width=True)
g3.plotly_chart(line("p1p2_frt", "P1/P2 median first response", "Hours", SERIES[2]), use_container_width=True)
note("The last week (28 Sep) has only 3 days of data, so its volume is partial. "
     "Backlog counts a reopened ticket as open from creation to final close.")

with st.expander("Weekly table"):
    st.dataframe(weekly, hide_index=True, use_container_width=True, column_config={
        "week": st.column_config.DateColumn("Week of", format="D MMM"),
        "volume": "Created", "backlog": "Backlog",
        "med_ttr": st.column_config.NumberColumn("Median close (h)", format="%.1f"),
        **{c: st.column_config.NumberColumn(lbl, format="percent") for c, lbl in [
            ("esc_pct", "Escalated"), ("wasted_pct", "Returned unfixed"), ("reopen_pct", "Reopened"),
            ("csat_resp_rate", "CSAT response")]},
        "csat": st.column_config.NumberColumn("CSAT", format="%.2f"),
        "p1p2_frt": st.column_config.NumberColumn("P1/P2 first response (h)", format="%.2f"),
    })

# ------------------------------------------------------------------ agents
section("Agents")
st.caption("Highlighted: escalation rate ≥ 50%, returned unfixed ≥ 70%, or reopen rate ≥ 20%.")
agents = m.by_agent(df)[["assigned_agent", "volume", "esc_pct", "wasted_pct", "reopen_pct",
                         "reopen_pct_non_esc", "med_first_close_non_esc_h", "csat", "open_now"]]
RULES = {"esc_pct": 0.5, "wasted_pct": 0.7, "reopen_pct": 0.2, "reopen_pct_non_esc": 0.2}


def flag(row):
    return [f"background-color: {C['bad_tint']}; color: {C['bad']}; font-weight: 600"
            if c in RULES and row[c] >= RULES[c] else "" for c in row.index]


st.dataframe(
    agents.style.apply(flag, axis=1).format({
        "esc_pct": "{:.0%}", "wasted_pct": "{:.0%}", "reopen_pct": "{:.0%}",
        "reopen_pct_non_esc": "{:.0%}", "med_first_close_non_esc_h": "{:.1f}h", "csat": "{:.2f}"}),
    hide_index=True, use_container_width=True,
    column_config={"assigned_agent": "Agent", "volume": "Tickets", "esc_pct": "Escalated",
                   "wasted_pct": "Returned unfixed", "reopen_pct": "Reopened",
                   "reopen_pct_non_esc": "Reopened (not escalated)",
                   "med_first_close_non_esc_h": "Median first close (not escalated)", "csat": "CSAT",
                   "open_now": "Open now"},
)

# ------------------------------------------------------------------ categories / templates
section("Where wasted escalations come from")
tab1, tab2 = st.tabs(["By category", "By issue template"])
cols = ["volume", "escalations", "wasted", "wasted_pct", "handoffs", "reopen_pct", "csat", "open_now"]
cfg = {"volume": "Tickets", "escalations": "Escalated", "wasted": "Returned unfixed",
       "wasted_pct": st.column_config.ProgressColumn("Share unfixed", format="percent", min_value=0, max_value=1),
       "handoffs": "Eng handoffs", "reopen_pct": st.column_config.NumberColumn("Reopened", format="percent"),
       "csat": st.column_config.NumberColumn("CSAT", format="%.2f"), "open_now": "Open now",
       "category": "Category", "template": "Issue template"}
with tab1:
    st.dataframe(m.by_category(df).sort_values("wasted", ascending=False)[["category"] + cols],
                 hide_index=True, use_container_width=True, column_config=cfg)
with tab2:
    st.dataframe(m.by_template(df).sort_values("wasted", ascending=False)[["template", "category"] + cols],
                 hide_index=True, use_container_width=True, column_config=cfg)
