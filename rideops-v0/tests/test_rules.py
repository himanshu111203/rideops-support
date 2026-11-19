from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from conftest import make_hist

from src.rules import (CONFIG, DEFAULT_THRESHOLDS as D, DUP, ESCALATE, ESCALATE_CHECKLIST, FIXED, HOWTO,
                       INFO, LINK, RESOLVE_L1, history_stats, recommend, recommend_for_ticket)

NO_LINK_SIGNALS = replace(D, min_live=0, use_recent_dup=False)


def rows(**counts):
    """rows(Fixed=7, DUP=3) -> list of closed escalations with those outcomes, closed 5 days ago."""
    out = []
    for outcome, n in counts.items():
        out += [{"outcome": outcome}] * n
    return out


OUT = {"FIXED": FIXED, "DUP": DUP, "CONFIG": CONFIG, "HOWTO": HOWTO, "INFO": INFO}


def hist(days_ago_closed=5, **counts):
    rs = []
    for k, n in counts.items():
        rs += [{"outcome": OUT[k], "days_ago_closed": days_ago_closed}] * n
    return rs


def rec(rs, th=D, template="Tpl A", category="Cat A", **kw):
    h, t = make_hist(rs)
    return recommend(h, template, category, t, th=th, **kw)


# ---------------------------------------------------------------- 5.1 rule logic
def test_live_eng_links():
    rs = hist(FIXED=6) + [{"outcome": FIXED, "open": True, "created_days_ago": 2, "eng_ticket_id": "ENG-LIVE"}]
    r = rec(rs)
    assert r.action == LINK
    assert "ENG-LIVE" in r.eng_ids


def test_recent_dup_links():
    rs = hist(FIXED=6) + [{"outcome": DUP, "days_ago_closed": 10, "eng_ticket_id": "ENG-DUP"}]
    r = rec(rs)
    assert r.action == LINK and "ENG-DUP" in r.eng_ids


def test_old_dup_ignored():
    rs = hist(FIXED=6) + [{"outcome": DUP, "days_ago_closed": 45}]
    r = rec(rs)
    assert r.action != LINK
    assert r.action == ESCALATE


@pytest.mark.parametrize("dups,total,expected", [(3, 10, LINK), (29, 100, ESCALATE)])
def test_dup_rate_threshold(dups, total, expected):
    rs = hist(days_ago_closed=60, DUP=dups, FIXED=total - dups)
    r = rec(rs, th=NO_LINK_SIGNALS)
    assert r.stats["tpl_dup_rate"] == pytest.approx(dups / total)
    assert r.action == expected


def test_config_branch():
    r = rec(hist(CONFIG=3, HOWTO=1, FIXED=6))
    assert r.action == RESOLVE_L1
    assert len(r.checklist) > 0


def test_info_branch():
    r = rec(hist(INFO=3, FIXED=7))
    assert r.action == ESCALATE_CHECKLIST
    assert len(r.checklist) > 0


def test_default_escalate():
    r = rec(hist(FIXED=8, INFO=1, CONFIG=1))
    assert r.action == ESCALATE


def test_priority_order():
    r = rec(hist(days_ago_closed=60, DUP=4, CONFIG=4, FIXED=2), th=NO_LINK_SIGNALS)
    assert r.action == LINK


def test_low_confidence():
    rs = hist(FIXED=4) + [{"outcome": CONFIG, "template": "Tpl B"}] * 6
    r = rec(rs)
    assert r.stats["tpl_n_esc"] == 4
    assert r.low_confidence and r.scope == "category"
    assert r.action == RESOLVE_L1          # category: 6 config of 10
    assert "this category" in r.reason


@pytest.mark.parametrize("counts,needle", [
    (dict(days_ago_closed=60, DUP=4, FIXED=6), "duplicate rate 40%"),
    (dict(CONFIG=4, FIXED=6), "40%"),
    (dict(INFO=3, FIXED=7), "30%"),
    (dict(FIXED=8, CONFIG=2), "80%"),
])
def test_reason_text(counts, needle):
    r = rec(hist(**counts), th=NO_LINK_SIGNALS)
    assert needle.lower() in r.reason.lower()


# ---------------------------------------------------------------- v2: smoothing
def test_smoothing_pulls_small_template_toward_category():
    # Template A: 5 escalations, 2 duplicates (raw 40%). Category: 20 more, all Fixed.
    rs = (hist(days_ago_closed=60, DUP=2, FIXED=3)
          + [{"outcome": FIXED, "template": "Tpl B", "days_ago_closed": 60}] * 20)
    h, t = make_hist(rs)
    s = history_stats(h, "Tpl A", "Cat A", t)
    assert s["tpl_dup_rate"] == pytest.approx(0.40)
    assert s["cat_dup_rate"] == pytest.approx(2 / 25)
    assert s["tpl_s_dup_rate"] < s["tpl_dup_rate"]          # shrunk...
    assert s["tpl_s_dup_rate"] > s["cat_s_dup_rate"]        # ...but not all the way
    r = recommend(h, "Tpl A", "Cat A", t, th=NO_LINK_SIGNALS)
    assert r.action != LINK                                 # 40% raw no longer triggers on its own


def test_smoothing_converges_with_more_data():
    big = hist(days_ago_closed=60, DUP=40, FIXED=60) + \
        [{"outcome": FIXED, "template": "Tpl B", "days_ago_closed": 60}] * 100
    h, t = make_hist(big)
    s = history_stats(h, "Tpl A", "Cat A", t)
    assert abs(s["tpl_s_dup_rate"] - s["tpl_dup_rate"]) < 0.02


# ---------------------------------------------------------------- v2: agent track record
def _agent_hist(wasted_by_agent: int, fixed_by_agent: int, team_fixed: int = 20):
    rs = hist(FIXED=8)                                                     # template history, all Fixed
    rs += [{"outcome": INFO, "agent": "Rahul", "template": "Tpl Z"}] * wasted_by_agent
    rs += [{"outcome": FIXED, "agent": "Rahul", "template": "Tpl Z"}] * fixed_by_agent
    rs += [{"outcome": FIXED, "agent": "Other", "template": "Tpl Z"}] * team_fixed
    return rs


AGENT_ONLY = replace(D, dup_rate=1.01, config_howto_rate=1.01, info_rate=1.01, min_live=0,
                     use_recent_dup=False, agent_wasted_rate=0.6)


def test_agent_rule_fires():
    r = rec(_agent_hist(16, 4), th=AGENT_ONLY, agent="Rahul")
    assert r.action == ESCALATE_CHECKLIST and r.trigger == "agent"
    assert "Rahul" in r.reason and "80%" in r.reason
    assert r.stats["agent_n_esc"] == 20


def test_agent_rule_needs_enough_history():
    r = rec(_agent_hist(5, 0), th=AGENT_ONLY, agent="Rahul")       # 5 < MIN_AGENT_N
    assert r.action == ESCALATE


def test_agent_rule_off_and_unknown_agent():
    off = replace(AGENT_ONLY, agent_wasted_rate=1.01)
    assert rec(_agent_hist(16, 4), th=off, agent="Rahul").action == ESCALATE
    assert rec(_agent_hist(16, 4), th=AGENT_ONLY, agent=None).action == ESCALATE


def test_agent_outcome_only_after_close():
    rs = _agent_hist(16, 4)
    rs += [{"outcome": INFO, "agent": "Rahul", "template": "Tpl Z", "open": True, "created_days_ago": 2}] * 10
    h, t = make_hist(rs)
    s = history_stats(h, "Tpl A", "Cat A", t, agent="Rahul")
    assert s["agent_n_esc"] == 20                          # still-open escalations don't count


def test_template_rules_take_priority_over_agent():
    rs = _agent_hist(16, 4) + hist(days_ago_closed=60, DUP=6)
    th = replace(AGENT_ONLY, dup_rate=0.3)
    r = rec(rs, th=th, agent="Rahul")
    assert r.action == LINK


# ---------------------------------------------------------------- 5.2 leakage
def test_no_future_tickets(df):
    t = pd.Timestamp("2026-08-15 09:00")
    tpl, cat = "Scheduled report email not received", "Report export failing"
    before = history_stats(df, tpl, cat, t)
    poisoned = df.copy()
    future = poisoned["created_at"] >= t
    poisoned.loc[future, "eng_outcome"] = DUP
    poisoned.loc[future, "escalated"] = True
    poisoned.loc[future, "template"] = tpl
    assert history_stats(poisoned, tpl, cat, t) == before


def test_outcome_only_after_close():
    rs = hist(FIXED=6) + [{"outcome": DUP, "closed_at": "2026-09-20 00:00", "created_days_ago": 3}]
    h, t = make_hist(rs)
    s = history_stats(h, "Tpl A", "Cat A", t)
    assert s["tpl_n_esc"] == 6 and s["tpl_dup_rate"] == 0
    assert s["live_eng"] == 1      # still with engineering at t


def test_self_excluded():
    rs = hist(FIXED=6) + [{"outcome": DUP, "ticket_id": "SUP-SELF", "days_ago_closed": 1}]
    h, t = make_hist(rs)
    with_self = history_stats(h, "Tpl A", "Cat A", t)
    without = history_stats(h, "Tpl A", "Cat A", t, exclude_id="SUP-SELF")
    assert with_self["tpl_n_esc"] == 7 and without["tpl_n_esc"] == 6


def test_shuffle_invariance(df):
    sample = df.sample(40, random_state=1)["ticket_id"].tolist()
    shuffled = df.sample(frac=1, random_state=7).reset_index(drop=True)
    for tid in sample:
        a, b = recommend_for_ticket(df, tid), recommend_for_ticket(shuffled, tid)
        assert (a.action, a.reason, a.eng_ids) == (b.action, b.reason, b.eng_ids)


def test_live_eng_at_t():
    rs = hist(FIXED=6) + [
        # closed today, but was still with engineering at t -> live
        {"outcome": FIXED, "closed_at": "2026-09-25 00:00", "created_days_ago": 2,
         "status": "Closed", "eng_ticket_id": "ENG-WAS-LIVE"},
        # status says open with engineering, but created after t -> not visible
        {"outcome": FIXED, "open": True, "created_days_ago": -2, "eng_ticket_id": "ENG-FUTURE"},
    ]
    h, t = make_hist(rs)
    s = history_stats(h, "Tpl A", "Cat A", t)
    assert s["live_eng_ids"] == ["ENG-WAS-LIVE"]
