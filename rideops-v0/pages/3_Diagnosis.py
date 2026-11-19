"""Diagnosis: the eight findings behind the v0, with charts."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

from src import diagnosis as dg  # noqa: E402
from src import metrics as m  # noqa: E402
from src.ui import C, get_df, inject_css, kpi_row, note, page_header, pct, style_fig  # noqa: E402

inject_css()
df = get_df()
h = m.headline(df)
mv = dg.monthly_volume(df)
NEUTRAL, HI, GOOD = "#94A3B8", C["accent"], C["primary"]

page_header("Lead · Diagnosis", "Why open tickets are up 60%",
            "Two drivers: more tickets with the same 8 agents, and slow escalations that often come back from "
            "engineering without a fix. Eight findings, each with the number behind it.")
kpi_row([
    {"label": "Open backlog", "value": f"{h['backlog_31_jul']} → {h['backlog_30_sep']}", "sub": "31 Jul → 30 Sep",
     "tone": "bad"},
    {"label": "Monthly volume", "value": f"{mv.iloc[0]} → {mv.iloc[-1]}",
     "sub": f"+{mv.iloc[-1] / mv.iloc[0] - 1:.0%}, same 8 agents"},
    {"label": "Escalations' share of open hours", "value": pct(h["open_hours_share_esc"]),
     "sub": f"from {df['escalated'].mean():.0%} of tickets", "tone": "accent"},
    {"label": "Escalations returned unfixed", "value": pct(h["wasted_pct"]),
     "sub": f"{h['wasted']} of {h['escalations']}", "tone": "accent"},
])


def finding(code: str, title: str, takeaway: str):
    st.markdown(f'<p class="rc-eyebrow" style="margin-top:28px">{code}</p>'
                f'<h2 style="margin:0 0 4px">{title}</h2><p class="rc-sub" style="margin-bottom:8px">{takeaway}</p>',
                unsafe_allow_html=True)


def bar(x, y, title, y_title, x_title, colors=None, fmt=".1f", horizontal=False, height=300):
    colors = colors or [GOOD] * len(x)
    kw = dict(orientation="h", y=list(x), x=list(y)) if horizontal else dict(x=list(x), y=list(y))
    hover = ("%{y}: %{x:" if horizontal else "%{x}: %{y:") + fmt + "}<extra></extra>"
    fig = go.Figure(go.Bar(**kw, marker=dict(color=colors, cornerradius=4), hovertemplate=hover))
    fig.update_layout(title=title, bargap=0.35)
    fig = style_fig(fig, x_title if horizontal else y_title, y_title if horizontal else x_title, height=height)
    fig.update_layout(hovermode="closest")
    (fig.update_yaxes if horizontal else fig.update_xaxes)(type="category")
    if fmt.endswith("%"):
        (fig.update_xaxes if horizontal else fig.update_yaxes)(tickformat=".0%")
    return fig


# D1
d1 = dg.d1_volume_by_category(df)
finding("D1", "Volume grew in every category",
        "Not one spike: every category grew between July and September, led by address/geocode and cab delays.")
st.plotly_chart(bar(d1["category"], d1["growth_jul_sep"], "Ticket growth, July → September", "Growth",
                    "Category", fmt=".0%", horizontal=True, height=340), use_container_width=True)

# D2
d2 = dg.d2_ttr_by_handoffs(df)
finding("D2", "Escalation is what makes tickets slow",
        f"Median close: {h['med_ttr_non_esc']:.1f}h without escalation vs {h['med_ttr_esc']:.1f}h with it, and "
        "every extra handoff adds about two days.")
cols = [NEUTRAL] + [HI] * (len(d2) - 1)
st.plotly_chart(bar(d2["eng_handoffs"].astype(str), d2["median_ttr_h"],
                    "Median hours to close, by engineering handoffs", "Hours", "Handoffs", colors=cols),
                use_container_width=True)

# D3 + D4
d3, d4 = dg.d3_outcomes(df), dg.d4_ttr_by_outcome(df)
finding("D3 · D4", "Most escalations shouldn't have gone to engineering, and they are the slowest",
        f"Only {h['fixed']} of {h['escalations']} were fixed. The rest cause {h['handoffs_wasted']} of "
        f"{h['handoffs_total']} handoffs ({h['handoffs_wasted'] / h['handoffs_total']:.0%}) and close slower than "
        "real fixes.")
c1, c2 = st.columns(2)
c1.plotly_chart(bar(d3["eng_outcome"], d3["tickets"], "Engineering's verdict on 486 escalations", "Tickets",
                    "Verdict", colors=[GOOD if o == "Fixed" else HI for o in d3["eng_outcome"]], fmt=".0f",
                    horizontal=True), use_container_width=True)
c2.plotly_chart(bar(d4["eng_outcome"], d4["median_ttr_h"], "Median hours to close, by verdict", "Hours",
                    "Verdict", colors=[GOOD if o == "Fixed" else HI for o in d4["eng_outcome"]],
                    horizontal=True), use_container_width=True)

# D5
dm, dt = dg.d5_duplicates(df)
finding("D5", "Duplicates of known issues are growing",
        f"{' → '.join(str(v) for v in dm.values)} per month, clustered in report export.")
c1, c2 = st.columns([1, 2])
c1.plotly_chart(bar(dm.index, dm.values, "Duplicate escalations per month", "Tickets", "Month",
                    colors=[NEUTRAL, NEUTRAL, HI], fmt=".0f"), use_container_width=True)
c2.dataframe(dt.head(8), hide_index=True, use_container_width=True, column_config={
    "category": "Category", "template": "Issue template", "escalations": "Escalated", "duplicates": "Duplicates",
    "dup_share": st.column_config.ProgressColumn("Share duplicate", format="percent", min_value=0, max_value=1)})

# D6
ag, pr = dg.d6_agents_priority(df)
finding("D6", "Escalation depends on the agent, not the ticket",
        "Escalation rate runs from 16% to 62% by agent, while P1 to P4 all escalate at about the same rate.")
c1, c2 = st.columns([2, 1])
c1.plotly_chart(bar(ag["assigned_agent"], ag["esc_pct"], "Escalation rate by agent", "% of tickets", "Agent",
                    colors=[HI if v >= 0.5 or v <= 0.2 else NEUTRAL for v in ag["esc_pct"]], fmt=".0%",
                    horizontal=True), use_container_width=True)
c2.plotly_chart(bar(pr["priority"], pr["escalated"] if "escalated" in pr else pr["esc_pct"],
                    "Escalation rate by priority", "% of tickets", "Priority", colors=[NEUTRAL] * len(pr),
                    fmt=".0%"), use_container_width=True)

# D7
finding("D7", "Fast closing is partly fake speed",
        "The fastest closer has the most reopens and the lowest CSAT.")
st.dataframe(dg.d7_fast_close(df), hide_index=True, use_container_width=True, column_config={
    "assigned_agent": "Agent",
    "med_first_close_non_esc_h": st.column_config.NumberColumn("Median first close, h (not escalated)", format="%.1f"),
    "reopen_pct_non_esc": st.column_config.NumberColumn("Reopened (not escalated)", format="percent"),
    "reopen_pct": st.column_config.NumberColumn("Reopened (all)", format="percent"),
    "csat": st.column_config.NumberColumn("CSAT", format="%.2f")})

# D8
d8 = dg.d8_client_feel(df)
cs = d8["csat_by_handoffs"]
finding("D8", "Clients feel the handoffs and reopens",
        f"CSAT falls from {cs.iloc[0]:.2f} to {cs.iloc[-1]:.2f} as handoffs go from 0 to 3. Reopened tickets score "
        f"{d8['csat_reopened'][True]:.2f} vs {d8['csat_reopened'][False]:.2f} and take "
        f"{d8['ttr_reopened'][True]:.0f}h vs {d8['ttr_reopened'][False]:.1f}h to close.")
st.plotly_chart(bar(cs.index.astype(str), cs.values, "CSAT by engineering handoffs", "CSAT (1–5)", "Handoffs",
                    colors=[GOOD] + [HI] * (len(cs) - 1), fmt=".2f"), use_container_width=True)
note(f"CSAT has a {pct(h['csat_resp_rate'])} response rate, so treat it as directional.")
