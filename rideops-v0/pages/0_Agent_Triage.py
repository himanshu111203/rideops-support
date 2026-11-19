"""Agent triage: should I escalate this ticket?"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st  # noqa: E402

from src.load import CUTOFF  # noqa: E402
from src.rules import DEFAULT_THRESHOLDS, recommend  # noqa: E402
from src.templates import UNKNOWN, match_template  # noqa: E402
from src.ui import (badge, get_df, get_tuned, icon, id_chips, inject_css, kpi_row, note,  # noqa: E402
                    page_header, pct, rec_card, section)

inject_css()
df = get_df()
tuned_th, _ = get_tuned()

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.markdown("**Queue**")
    agents = ["All agents"] + sorted(df["assigned_agent"].unique())
    agent = st.selectbox("Agent queue", agents, key="agent")
    th_choice = st.radio("Thresholds", ["Tuned on Jul–Aug", "Plan defaults"], key="th_choice")
    th = tuned_th if th_choice == "Tuned on Jul–Aug" else DEFAULT_THRESHOLDS
    with st.expander("Active thresholds"):
        st.json({k: v for k, v in th.__dict__.items()})
    st.caption(f"History as of the data pull, {CUTOFF:%d %b %Y %H:%M} IST. "
               "A rate threshold of 101% means that rule is off.")

page_header("Agent · Escalation check", "Should I escalate this ticket?",
            "Checks how similar tickets went when they were escalated before, and recommends escalating, "
            "linking to a known issue, or trying to resolve at L1 first.")

# ------------------------------------------------------------------ input
mode = st.radio("Ticket source", ["Open ticket", "Enter manually"], key="mode", horizontal=True,
                label_visibility="collapsed")
known_templates = set(df["template"])

if mode == "Open ticket":
    open_df = df[df["is_open"]].sort_values("created_at", ascending=False)
    if agent != "All agents":
        open_df = open_df[open_df["assigned_agent"] == agent]
    if open_df.empty:
        st.info("No open tickets in this queue.")
        st.stop()
    labels = {r.ticket_id: f"{r.ticket_id} · {r.priority} · {r.description}" for r in open_df.itertuples()}
    tid = st.selectbox(f"Open ticket ({len(open_df)} in this queue)", list(labels), format_func=labels.get,
                       key="ticket")
    row = df.loc[df["ticket_id"] == tid].iloc[0]
    template, category, exclude = row["template"], row["category"], tid
    ticket_agent = row["assigned_agent"]
    prio_tone = {"P1": "bad", "P2": "warn"}.get(row["priority"], "neutral")
    st.markdown(
        '<div class="rc-meta">'
        f'{badge(row["priority"], prio_tone)}'
        f'<span><b>{row["client_name"]}</b> · {row["client_tier"]}</span>'
        f'<span>{icon("user", 14)} {row["assigned_agent"]}</span>'
        f'<span>{icon("clock", 14)} {row["created_at"]:%d %b, %H:%M}</span>'
        f'<span>{row["category"]}</span>'
        f'<span>{row["status"]}</span></div>',
        unsafe_allow_html=True)
else:
    c1, c2 = st.columns([1, 2])
    category = c1.selectbox("Category", sorted(df["category"].unique()), key="manual_category")
    text = c2.text_input("Description", placeholder="e.g. Roster uploaded via Excel but 12 employees missing",
                         key="manual_text")
    if not text.strip():
        note("Type a description to get a recommendation.")
        st.stop()
    template, exclude = match_template(text, known_templates), None
    ticket_agent = None if agent == "All agents" else agent
    if ticket_agent is None:
        note("Pick an agent queue in the sidebar to include that agent's track record.")

rec = recommend(df, template, category, CUTOFF, exclude_id=exclude, th=th, agent=ticket_agent)

# ------------------------------------------------------------------ recommendation
section("Recommendation")
rec_card(rec)

s = rec.stats
p = "cat_s_" if rec.low_confidence else "tpl_s_"
n_hist = s["cat_n_esc"] if rec.low_confidence else s["tpl_n_esc"]
has = s["team_n_esc"] > 0
scope = "category" if rec.low_confidence else "issue"
kpi_row([
    {"label": f"Past escalations ({scope})", "value": n_hist},
    {"label": "Fixed by engineering", "value": pct(s[p + "fix_rate"]) if has else "–",
     "tone": "good" if has and s[p + "fix_rate"] >= 0.5 else None},
    {"label": "Duplicate of known issue", "value": pct(s[p + "dup_rate"]) if has else "–",
     "tone": "warn" if rec.trigger == "dup" else None},
    {"label": "Config / how-to", "value": pct(s[p + "config_howto_rate"]) if has else "–",
     "tone": "warn" if rec.trigger == "config" else None},
    {"label": "Insufficient info", "value": pct(s[p + "info_rate"]) if has else "–",
     "tone": "warn" if rec.trigger == "info" else None},
    {"label": "Agent: returned unfixed", "value": pct(s["agent_wasted_rate"]) if s["agent_n_esc"] else "–",
     "sub": f"team {pct(s['team_wasted_rate'])}" if s["agent_n_esc"] else "no agent selected",
     "tone": "warn" if rec.trigger == "agent" else None},
])
note("Rates are smoothed: an issue with few past escalations is blended with its category's rate, "
     "so a handful of tickets can't swing the advice.")

left, right = st.columns([3, 2], gap="large")
with left:
    if rec.eng_ids:
        section("Matching engineering tickets")
        id_chips(rec.eng_ids)
    if rec.checklist:
        section("Checklist before escalating" if rec.action != "Try resolving at L1 first"
                else "Configuration checks")
        for i, item in enumerate(rec.checklist):
            st.checkbox(item, key=f"chk_{rec.action}_{i}")
        note(rec.note)
with right:
    section("Issue template")
    st.code(template if template != UNKNOWN else "(no matching template)", language=None, wrap_lines=True)
    st.caption(f"{category} · open with engineering now: {s['live_eng']}")

section("History of this issue (escalations before now)")
hist = df[(df["category"] == category) & df["escalated"]] if template == UNKNOWN else \
    df[(df["template"] == template) & df["escalated"]]
hist = hist[(hist["created_at"] < CUTOFF) & (hist["ticket_id"] != exclude)].copy()
# An outcome isn't final until the ticket closes; don't show it for open tickets.
hist.loc[hist["final_closed_at"].isna(), "eng_outcome"] = "(pending: still open)"
st.dataframe(
    hist.sort_values("created_at", ascending=False)[
        ["ticket_id", "created_at", "client_name", "assigned_agent", "eng_ticket_id",
         "eng_outcome", "eng_handoffs", "ttr_h"]],
    hide_index=True, use_container_width=True, height=280,
    column_config={
        "ticket_id": "Ticket", "created_at": st.column_config.DatetimeColumn("Created", format="D MMM, HH:mm"),
        "client_name": "Client", "assigned_agent": "Agent", "eng_ticket_id": "Eng ticket",
        "eng_outcome": "Engineering verdict", "eng_handoffs": "Handoffs",
        "ttr_h": st.column_config.NumberColumn("Hours to close", format="%.1f"),
    },
)
