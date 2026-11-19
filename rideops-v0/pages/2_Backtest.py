"""Backtest: thresholds learned on Jul–Aug, tested on September escalations."""
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from src import backtest as bt  # noqa: E402
from src.ui import (callout, get_df, get_test_table, get_tuned, get_walk_forward, inject_css,  # noqa: E402
                    kpi_row, note, page_header, pct, section)

inject_css()
df = get_df()
tuned_th, tune_res = get_tuned()
table = get_test_table()

page_header("Lead · Backtest", "Would the check have helped in September?",
            "Every September escalation is scored as of its creation time, using only history available then. "
            "<b>Flagged</b> = the tool would not have sent it straight to engineering. Thresholds were picked on "
            "Jul–Aug only, by the lower 95% confidence bound of precision.")

res = bt.run_backtest(df, tuned_th, table)
c = res["confusion"]
kpi_row([
    {"label": "September escalations", "value": res["test_size"], "sub": f"{res['test_wasted']} returned unfixed"},
    {"label": "Flagged by the check", "value": c["flagged"]},
    {"label": "Catch rate", "value": pct(c["catch_rate"]), "sub": f"{c['TP']} of {res['test_wasted']} unfixed"},
    {"label": "Precision", "value": f"{c['precision']:.1%}", "sub": f"baseline {res['baseline_precision']:.1%}",
     "tone": "good" if res["claim_supported"] else "bad"},
    {"label": "Fixed tickets held back", "value": c["held_back_fixed"], "tone": "warn"},
])

# ------------------------------------------------------------------ verdicts
section("What the backtest supports")
v1, v2 = st.columns(2)
with v1:
    body = (f"Precision {c['precision']:.1%} vs {res['baseline_precision']:.1%} for flagging everything "
            f"(p = {res['p_value_vs_baseline']:.2f}). ")
    if res["claim_supported"] and res["p_value_vs_baseline"] < 0.05:
        callout("good", "check", "Wasted escalations: beats the baseline", body)
    elif res["claim_supported"]:
        callout("warn", "alert", "Wasted escalations: ahead, but within noise",
                body + "Don't claim the tool reliably predicts wasted escalations.")
    else:
        callout("bad", "x", "Wasted escalations: claim dropped", body + "Does not beat the baseline.")
with v2:
    if res["link_flagged"] and res["link_dup_p_value"] < 0.05:
        callout("good", "check", "Duplicate detection: supported",
                f"{res['link_duplicates']} of {res['link_flagged']} 'Link to known issue' flags were real duplicates "
                f"({pct(res['link_dup_precision'])}) vs a {pct(res['dup_base_rate'])} base rate: "
                f"<b>{res['link_dup_lift']:.1f}× lift</b> (p = {res['link_dup_p_value']:.1g}). Lead with this.")
    else:
        callout("neutral", "info", "Duplicate detection", "Not enough evidence on this setting.")
note(f"Proxy saving (no engineering effort logs exist): {res['handoffs_avoided']} engineering handoffs avoided; "
     f"about {res['proxy_hours_saved']:,.0f} ticket-hours (caught × {res['proxy_hours_per_catch']:.0f}h, the Jul–Aug "
     "gap in median close time between unfixed and Fixed escalations).")

pct_cfg = {"catch_rate": st.column_config.NumberColumn("Catch rate", format="percent"),
           "precision": st.column_config.NumberColumn("Precision", format="percent"),
           "baseline_precision": st.column_config.NumberColumn("Baseline", format="percent"),
           "held_back_fixed": "Fixed held back", "flagged": "Flagged"}
a, b = st.columns(2)
with a:
    section("Against naive baselines")
    base = res["baselines"].copy()
    rules_row = pd.DataFrame([{"strategy": "Tuned rules", "flagged": c["flagged"], "TP": c["TP"],
                               "catch_rate": c["catch_rate"], "precision": c["precision"],
                               "held_back_fixed": c["held_back_fixed"]}])
    st.dataframe(pd.concat([base, rules_row]), hide_index=True, use_container_width=True,
                 column_config={"strategy": "Strategy", "TP": "Caught"} | pct_cfg)
with b:
    section("By rule that fired")
    st.dataframe(res["by_trigger"], hide_index=True, use_container_width=True,
                 column_config={"trigger": "Rule", "wasted": "Unfixed", "duplicates": "Real duplicates"} | pct_cfg)
    st.caption("dup = duplicate rate · agent = agent's track record · config = config/how-to rate · "
               "info = insufficient-info rate · recent / live = recent duplicate or open engineering ticket")

# ------------------------------------------------------------------ walk-forward
section("Walk-forward: does it hold in more than one month?")
wf = get_walk_forward()
st.dataframe(wf.drop(columns=["thresholds"]), hide_index=True, use_container_width=True,
             column_config={"test_month": "Test month", "escalations": "Escalations", "TP": "Caught",
                            "FP": "Fixed flagged", "beats_baseline": "Beats baseline"} | pct_cfg)
note(f"Thresholds are re-tuned on the months before each test month. Pooled: precision "
     f"{wf.attrs['pooled_precision']:.1%} vs baseline {wf.attrs['pooled_baseline']:.1%}.")

# ------------------------------------------------------------------ slider
section("Try other thresholds")
st.caption("Exploration only: results are on the September test set, so choosing thresholds here would leak. "
           "101% switches a rule off.")
s = st.columns(6)
steps = [0.1, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, bt.OFF]
fmt = lambda v: f"{v:.0%}"  # noqa: E731
dup = s[0].select_slider("Duplicate rate ≥", steps, value=tuned_th.dup_rate, key="dup", format_func=fmt)
cfg = s[1].select_slider("Config + how-to ≥", steps, value=tuned_th.config_howto_rate, key="cfg",
                         format_func=fmt)
info = s[2].select_slider("Insufficient info ≥", steps, value=tuned_th.info_rate, key="info", format_func=fmt)
agent_th = s[3].select_slider("Agent unfixed ≥", steps, value=tuned_th.agent_wasted_rate,
                              key="agent_th", format_func=fmt)
live = s[4].select_slider("Open with eng ≥ (0 = off)", [0, 1, 2, 3], value=tuned_th.min_live, key="live")
recent = s[5].checkbox("Recent duplicate (30 days) links", value=tuned_th.use_recent_dup, key="recent")

th = replace(tuned_th, dup_rate=dup, config_howto_rate=cfg, info_rate=info, agent_wasted_rate=agent_th,
             min_live=live, use_recent_dup=recent)
cc = bt.confusion(bt.apply_rules(table, th))
st.dataframe(pd.DataFrame([{k: cc[k] for k in ("flagged", "TP", "FP", "FN", "TN", "catch_rate",
                                                 "precision", "held_back_fixed")}]),
             hide_index=True, use_container_width=True, key="slider_table",
             column_config={"TP": "Caught", "FP": "Fixed flagged", "FN": "Unfixed missed",
                            "TN": "Fixed passed"} | pct_cfg)

with st.expander("Threshold grid on September (reference)"):
    st.dataframe(bt.threshold_grid(df, table), hide_index=True, use_container_width=True, column_config=pct_cfg)
with st.expander("Tuning grid on Jul–Aug (how thresholds were picked), top 15"):
    st.dataframe(tune_res.head(15).round(3), hide_index=True, use_container_width=True)
with st.expander("Scored September escalations"):
    st.dataframe(res["scored"], hide_index=True, use_container_width=True)
