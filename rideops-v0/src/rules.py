"""Recommendation engine: should L1 escalate this ticket to engineering?

For a ticket created at time t, history is built ONLY from information that was
available at t:
  * tickets created before t (the ticket itself is excluded);
  * an engineering outcome counts only if that ticket was finally closed before t
    (there is no timestamp for engineering's verdict, and open tickets already carry one);
  * "open with engineering" = escalated, created before t, and not finally closed by t.
    It never reads today's `status` column.

Known leak we accept and state: whether a past ticket was escalated is taken from the
final data, because there is no escalation timestamp.

Signals (v2):
  * Outcome rates per issue template, *smoothed* toward the category rate, which is in
    turn smoothed toward the team-wide rate. A template with 6 past escalations no
    longer swings the recommendation on its own.
  * The agent's own track record: share of their past escalations that came back
    without a fix, smoothed toward the team rate.
  * Duplicates: smoothed duplicate rate, a duplicate verdict in the last 30 days, or a
    ticket of the same issue currently open with engineering.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

import pandas as pd

from src.checklists import ASSUMPTION_NOTE, checklist_for, config_checks_for
from src.templates import UNKNOWN

LINK = "Link to known issue"
RESOLVE_L1 = "Try resolving at L1 first"
ESCALATE_CHECKLIST = "Escalate only with the checklist completed"
ESCALATE = "Escalate"
ACTIONS = [LINK, RESOLVE_L1, ESCALATE_CHECKLIST, ESCALATE]

DUP = "Duplicate of known issue"
CONFIG = "Config issue - returned to L1"
HOWTO = "Not a bug - how-to"
INFO = "Insufficient info - returned to L1"
FIXED = "Fixed"

# Smoothing strengths: "worth this many pseudo-escalations at the parent rate".
M_TPL = 5       # template -> category
M_CAT = 10      # category -> team
M_AGENT = 10    # agent -> team
MIN_AGENT_N = 10  # agent rule needs at least this many past escalations with a known outcome
EPS = 1e-9      # thresholds are inclusive; guard against float rounding


@dataclass(frozen=True)
class Thresholds:
    dup_rate: float = 0.30
    config_howto_rate: float = 0.35
    info_rate: float = 0.25
    agent_wasted_rate: float = 0.65  # > 1 switches the agent rule off
    min_live: int = 1          # live_eng >= min_live links to known issue; 0 disables the rule
    use_recent_dup: bool = True
    recent_days: int = 30
    min_n: int = 5             # fewer past escalations than this -> category-level rates


DEFAULT_THRESHOLDS = Thresholds()


@dataclass
class Recommendation:
    action: str
    reason: str
    template: str
    category: str
    low_confidence: bool
    scope: str                          # "template" or "category"
    eng_ids: list[str] = field(default_factory=list)
    checklist: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    note: str = ""
    trigger: str = ""                   # which rule fired: dup / live / recent / config / info / agent / none

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- stats
RATE_KEYS = ("dup_rate", "config_howto_rate", "info_rate", "fix_rate")


def _counts(known: pd.DataFrame) -> dict:
    vc = known["eng_outcome"].value_counts()
    c = lambda *outs: float(sum(vc.get(o, 0) for o in outs))  # noqa: E731
    return {"n": len(known), "dup_rate": c(DUP), "config_howto_rate": c(CONFIG, HOWTO),
            "info_rate": c(INFO), "fix_rate": c(FIXED)}


def _raw(counts: dict) -> dict:
    n = counts["n"]
    return {k: (counts[k] / n if n else 0.0) for k in RATE_KEYS}


def _smooth(counts: dict, prior: dict, m: float) -> dict:
    n = counts["n"]
    return {k: (counts[k] + m * prior[k]) / (n + m) for k in RATE_KEYS}


def history_stats(df: pd.DataFrame, template: str, category: str, t,
                  exclude_id: str | None = None, recent_days: int = 30,
                  agent: str | None = None) -> dict:
    """Everything the rules need, using only information available at time t."""
    t = pd.Timestamp(t)
    past = df[df["created_at"] < t]
    if exclude_id is not None:
        past = past[past["ticket_id"] != exclude_id]
    esc = past[past["escalated"]]
    known = esc[esc["final_closed_at"] < t]           # outcome visible only after close

    tpl_known = known[known["template"] == template] if template != UNKNOWN else known.iloc[0:0]
    cat_known = known[known["category"] == category]

    g_c, cat_c, tpl_c = _counts(known), _counts(cat_known), _counts(tpl_known)
    g = _raw(g_c)
    cat_s = _smooth(cat_c, g, M_CAT)
    tpl_s = _smooth(tpl_c, cat_s, M_TPL)

    out = {"team_n_esc": g_c["n"], "team_wasted_rate": 1 - g["fix_rate"] if g_c["n"] else 0.0}
    out.update({"tpl_n_esc": tpl_c["n"], "cat_n_esc": cat_c["n"]})
    out.update({f"tpl_{k}": v for k, v in _raw(tpl_c).items()})
    out.update({f"cat_{k}": v for k, v in _raw(cat_c).items()})
    out.update({f"tpl_s_{k}": v for k, v in tpl_s.items()})
    out.update({f"cat_s_{k}": v for k, v in cat_s.items()})

    # Agent track record
    if agent is not None and "assigned_agent" in known.columns:
        ag = known[known["assigned_agent"] == agent]
        n_a, w_a = len(ag), float((ag["eng_outcome"] != FIXED).sum())
        out["agent"] = agent
        out["agent_n_esc"] = n_a
        out["agent_wasted_rate"] = w_a / n_a if n_a else 0.0
        out["agent_s_wasted_rate"] = (w_a + M_AGENT * out["team_wasted_rate"]) / (n_a + M_AGENT)
    else:
        out.update({"agent": agent, "agent_n_esc": 0, "agent_wasted_rate": 0.0,
                    "agent_s_wasted_rate": 0.0})

    if template != UNKNOWN:
        tpl_esc = esc[esc["template"] == template]
        live = tpl_esc[tpl_esc["final_closed_at"].isna() | (tpl_esc["final_closed_at"] > t)]
        recent = tpl_known[(tpl_known["eng_outcome"] == DUP)
                           & (tpl_known["final_closed_at"] >= t - pd.Timedelta(days=recent_days))]
        last_dups = tpl_known[tpl_known["eng_outcome"] == DUP].nlargest(3, "final_closed_at")
        out["live_eng_ids"] = sorted(live["eng_ticket_id"].dropna().tolist())
        out["recent_dup_ids"] = sorted(recent["eng_ticket_id"].dropna().tolist())
        out["last_dup_ids"] = sorted(last_dups["eng_ticket_id"].dropna().tolist())
    else:
        out["live_eng_ids"], out["recent_dup_ids"], out["last_dup_ids"] = [], [], []
    out["live_eng"] = len(out["live_eng_ids"])
    out["recent_dup"] = len(out["recent_dup_ids"]) > 0
    return out


# --------------------------------------------------------------------------- decision
def _pct(x: float) -> str:
    return f"{x:.0%}"


def _ge(x: float, th: float) -> bool:
    return x >= th - EPS


def decide(stats: dict, template: str, category: str,
           th: Thresholds = DEFAULT_THRESHOLDS) -> Recommendation:
    low_conf = stats["tpl_n_esc"] < th.min_n
    scope = "category" if low_conf else "template"
    p = "cat_s_" if low_conf else "tpl_s_"
    n = stats["cat_n_esc"] if low_conf else stats["tpl_n_esc"]
    dup, cfg, info, fix = (stats[p + k] for k in RATE_KEYS)
    what = "this category" if low_conf else "this issue"
    has_hist = stats["team_n_esc"] > 0
    base = dict(template=template, category=category, low_confidence=low_conf, scope=scope,
                stats=stats, note=ASSUMPTION_NOTE)
    n_txt = f"{n} past escalation{'s' if n != 1 else ''} of {what}"

    live_ids, recent_ids = stats["live_eng_ids"], stats["recent_dup_ids"]
    live_hit = th.min_live > 0 and stats["live_eng"] >= th.min_live
    recent_hit = th.use_recent_dup and stats["recent_dup"]
    dup_hit = has_hist and _ge(dup, th.dup_rate)

    if live_hit or recent_hit or dup_hit:
        parts = []
        if dup_hit:
            parts.append(f"duplicate rate {_pct(dup)} across {n_txt} "
                         f"(threshold {_pct(th.dup_rate)})")
        if recent_hit:
            parts.append(f"marked 'duplicate of known issue' in the last {th.recent_days} days: "
                         + ", ".join(recent_ids[:5]))
        if live_hit:
            parts.append(f"{stats['live_eng']} ticket(s) of this issue open with engineering now: "
                         + ", ".join(live_ids[:5]))
        trig = "dup" if dup_hit else ("recent" if recent_hit else "live")
        ids = sorted(set(live_ids) | set(recent_ids)) or stats["last_dup_ids"]
        return Recommendation(action=LINK, reason="; ".join(parts).capitalize() + ".",
                              eng_ids=ids, checklist=[], trigger=trig, **base)

    if has_hist and _ge(cfg, th.config_howto_rate):
        return Recommendation(
            action=RESOLVE_L1, trigger="config",
            reason=(f"Config issue + how-to rate {_pct(cfg)} across {n_txt} "
                    f"(threshold {_pct(th.config_howto_rate)}). Check the configuration first."),
            checklist=config_checks_for(category), **base)

    if has_hist and _ge(info, th.info_rate):
        return Recommendation(
            action=ESCALATE_CHECKLIST, trigger="info",
            reason=(f"Insufficient-info rate {_pct(info)} across {n_txt} "
                    f"(threshold {_pct(th.info_rate)}). Complete the checklist before escalating."),
            checklist=checklist_for(category), **base)

    a_rate = stats["agent_s_wasted_rate"]
    if stats["agent_n_esc"] >= MIN_AGENT_N and _ge(a_rate, th.agent_wasted_rate):
        return Recommendation(
            action=ESCALATE_CHECKLIST, trigger="agent",
            reason=(f"{stats['agent']}'s past escalations came back without a fix "
                    f"{_pct(stats['agent_wasted_rate'])} of the time ({stats['agent_n_esc']} escalations; "
                    f"team {_pct(stats['team_wasted_rate'])}, threshold {_pct(th.agent_wasted_rate)}). "
                    "Get a second check and complete the checklist before escalating."),
            checklist=checklist_for(category), **base)

    reason = (f"Fix rate {_pct(fix)} across {n_txt}; no known-issue, config, missing-info "
              f"or track-record pattern above threshold." if has_hist else
              "No past escalations with a known outcome; escalate with the standard checklist.")
    return Recommendation(action=ESCALATE, reason=reason, checklist=checklist_for(category),
                          trigger="none", **base)


def recommend(df: pd.DataFrame, template: str, category: str, t,
              exclude_id: str | None = None,
              th: Thresholds = DEFAULT_THRESHOLDS, agent: str | None = None) -> Recommendation:
    stats = history_stats(df, template, category, t, exclude_id, th.recent_days, agent)
    return decide(stats, template, category, th)


def recommend_for_ticket(df: pd.DataFrame, ticket_id: str, t=None,
                         th: Thresholds = DEFAULT_THRESHOLDS) -> Recommendation:
    """Recommendation for an existing ticket, as of its creation time (or t if given)."""
    row = df.loc[df["ticket_id"] == ticket_id].iloc[0]
    return recommend(df, row["template"], row["category"],
                     row["created_at"] if t is None else t, exclude_id=ticket_id, th=th,
                     agent=row["assigned_agent"])
