"""Backtest: learn on 2 Jul - 31 Aug, test on September escalations.

Each escalated ticket is scored as of its own creation time, using only history
available then (see rules.history_stats). A ticket is "flagged" when the tool would
not have sent it straight to engineering (any action other than Escalate).

  catch rate      = TP / wasted escalations in the test set
  precision       = TP / flagged
  held-back fixed = FP (genuinely Fixed tickets the tool would have slowed down)

Thresholds are chosen on training data only, by the *lower confidence bound* of
precision (Wilson, one-sided 95%) among settings that flag at least MIN_FLAG_SHARE of
training escalations. That penalises settings that look precise on a handful of
tickets, which is what over-fitted in v1.

Walk-forward validation repeats the exercise per month: tune on everything before
August -> test August; tune on everything before September -> test September.

Engineering effort isn't logged, so savings are a proxy: handoffs avoided on caught
tickets, and extra hours = caught tickets x (median close time of wasted escalations
minus median close time of Fixed ones), both medians from the training period.
"""
from __future__ import annotations

import itertools
import math
from dataclasses import asdict, replace

import pandas as pd

from src.rules import ACTIONS, DEFAULT_THRESHOLDS, ESCALATE, Thresholds, decide, history_stats

SPLIT = pd.Timestamp("2026-09-01 00:00")
FOLDS = [  # (train_end = test_start, test_end)
    (pd.Timestamp("2026-08-01 00:00"), pd.Timestamp("2026-09-01 00:00")),
    (pd.Timestamp("2026-09-01 00:00"), pd.Timestamp("2026-10-01 00:00")),
]

OFF = 1.01  # a rate threshold above 100% switches that rule off

GRID = {
    "dup_rate": [0.20, 0.25, 0.30, 0.40, OFF],
    "config_howto_rate": [0.30, 0.40, OFF],
    "info_rate": [0.25, 0.35, OFF],
    "agent_wasted_rate": [0.55, 0.60, 0.65, 0.70, OFF],
    "min_live": [0, 1],
    "use_recent_dup": [True, False],
}
# Tuning must flag at least this share of training escalations, so "flag 3 tickets
# at 100% precision" can't win.
MIN_FLAG_SHARE = 0.15
Z = 1.645  # one-sided 95%


def split(df: pd.DataFrame, at: pd.Timestamp = SPLIT) -> tuple[pd.DataFrame, pd.DataFrame]:
    esc = df[df["escalated"]]
    return esc[esc["created_at"] < at], esc[esc["created_at"] >= at]


def stats_table(df: pd.DataFrame, tickets: pd.DataFrame, recent_days: int = 30) -> list[dict]:
    """History stats for each ticket as of its creation (computed once; thresholds applied later)."""
    out = []
    for row in tickets.sort_values("created_at").itertuples(index=False):
        s = history_stats(df, row.template, row.category, row.created_at, row.ticket_id,
                          recent_days, agent=row.assigned_agent)
        out.append({"ticket_id": row.ticket_id, "template": row.template, "category": row.category,
                    "agent": row.assigned_agent, "created_at": row.created_at,
                    "wasted": bool(row.wasted_escalation), "eng_outcome": row.eng_outcome,
                    "eng_handoffs": int(row.eng_handoffs), "stats": s})
    return out


def apply_rules(table: list[dict], th: Thresholds) -> pd.DataFrame:
    rows = []
    for r in table:
        rec = decide(r["stats"], r["template"], r["category"], th)
        rows.append({k: r[k] for k in ("ticket_id", "template", "category", "agent", "created_at",
                                       "wasted", "eng_outcome", "eng_handoffs")}
                    | {"action": rec.action, "trigger": rec.trigger,
                       "low_confidence": rec.low_confidence,
                       "flagged": rec.action != ESCALATE, "reason": rec.reason})
    return pd.DataFrame(rows, columns=["ticket_id", "template", "category", "agent", "created_at",
                                       "wasted", "eng_outcome", "eng_handoffs", "action", "trigger",
                                       "low_confidence", "flagged", "reason"])


def _binom_sf(k: int, n: int, p: float) -> float:
    """P(X >= k) for X ~ Binomial(n, p): exact, no scipy needed."""
    return float(sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1)))


def wilson_lower(tp: int, n: int, z: float = Z) -> float:
    if n == 0:
        return 0.0
    p = tp / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (centre - margin) / denom


def confusion(scored: pd.DataFrame) -> dict:
    f, w = scored["flagged"].astype(bool), scored["wasted"].astype(bool)
    tp, fp = int((f & w).sum()), int((f & ~w).sum())
    fn, tn = int((~f & w).sum()), int((~f & ~w).sum())
    flagged, wasted = tp + fp, tp + fn
    prec = tp / flagged if flagged else float("nan")
    rec = tp / wasted if wasted else float("nan")
    f05 = (1.25 * prec * rec / (0.25 * prec + rec)) if flagged and tp else 0.0
    return {"TP": tp, "FP": fp, "FN": fn, "TN": tn, "flagged": flagged, "n": len(scored),
            "catch_rate": rec, "precision": prec, "precision_lb": wilson_lower(tp, flagged),
            "held_back_fixed": fp, "f05": f05}


def _fast_confusion(table: list[dict], th: Thresholds) -> dict:
    """Confusion without building a DataFrame (used inside the tuning loop)."""
    tp = fp = fn = tn = 0
    for r in table:
        flagged = decide(r["stats"], r["template"], r["category"], th).action != ESCALATE
        if flagged and r["wasted"]:
            tp += 1
        elif flagged:
            fp += 1
        elif r["wasted"]:
            fn += 1
        else:
            tn += 1
    flagged, wasted = tp + fp, tp + fn
    return {"TP": tp, "FP": fp, "FN": fn, "TN": tn, "flagged": flagged, "n": len(table),
            "catch_rate": tp / wasted if wasted else float("nan"),
            "precision": tp / flagged if flagged else float("nan"),
            "precision_lb": wilson_lower(tp, flagged), "held_back_fixed": fp}


def _proxy_hours_per_catch(df: pd.DataFrame, train_end: pd.Timestamp = SPLIT) -> float:
    train = df[(df["created_at"] < train_end) & df["escalated"] & (df["final_closed_at"] < train_end)]
    return float(train.loc[train["wasted_escalation"], "ttr_h"].median()
                 - train.loc[train["fixed"], "ttr_h"].median())


def tune(df: pd.DataFrame, grid: dict | None = None,
         train_end: pd.Timestamp = SPLIT) -> tuple[Thresholds, pd.DataFrame]:
    """Pick thresholds on escalations created before `train_end` only.

    Rows created on/after train_end are dropped up front, so nothing from the test
    period can influence the choice. Objective: highest Wilson lower bound on precision
    among settings that flag >= MIN_FLAG_SHARE of training escalations; ties -> more
    caught, then closest to the default thresholds.
    """
    train_df = df[df["created_at"] < train_end].copy()
    train, _ = split(train_df, train_end)
    table = stats_table(train_df, train)
    grid = grid or GRID
    rows = []
    for combo in itertools.product(*grid.values()):
        th = replace(DEFAULT_THRESHOLDS, **dict(zip(grid.keys(), combo)))
        c = _fast_confusion(table, th)
        dist = sum(abs(float(getattr(th, k)) - float(getattr(DEFAULT_THRESHOLDS, k))) for k in grid)
        rows.append(dict(zip(grid.keys(), combo)) | c | {"dist_default": dist})
    res = pd.DataFrame(rows)
    res["eligible"] = res["flagged"] >= MIN_FLAG_SHARE * len(train)
    res = res.sort_values(["eligible", "precision_lb", "TP", "dist_default"],
                          ascending=[False, False, False, True]).reset_index(drop=True)
    best = res.iloc[0]
    th = replace(DEFAULT_THRESHOLDS, **{k: type(getattr(DEFAULT_THRESHOLDS, k))(best[k]) for k in grid})
    return th, res


def baselines(test: pd.DataFrame) -> pd.DataFrame:
    n, wasted = len(test), int(test["wasted_escalation"].sum())
    return pd.DataFrame([
        {"strategy": "Flag nothing", "flagged": 0, "TP": 0, "catch_rate": 0.0,
         "precision": float("nan"), "held_back_fixed": 0},
        {"strategy": "Flag everything", "flagged": n, "TP": wasted, "catch_rate": 1.0,
         "precision": wasted / n if n else float("nan"), "held_back_fixed": n - wasted},
    ])


def run_backtest(df: pd.DataFrame, th: Thresholds = DEFAULT_THRESHOLDS,
                 table: list[dict] | None = None) -> dict:
    """Score September escalations with thresholds `th`."""
    _, test = split(df)
    if table is None:
        table = stats_table(df, test, th.recent_days)
    scored = apply_rules(table, th)
    c = confusion(scored)
    caught = scored[scored["flagged"] & scored["wasted"]]
    per_catch = _proxy_hours_per_catch(df)
    by_action = (scored.groupby("action")
                 .agg(flagged=("ticket_id", "size"), wasted=("wasted", "sum"))
                 .reindex(ACTIONS).fillna(0).astype(int).reset_index())
    by_action["fixed_held_back"] = by_action["flagged"] - by_action["wasted"]
    by_action.loc[by_action["action"] == ESCALATE, "fixed_held_back"] = 0
    by_trigger = (scored[scored["flagged"]].groupby("trigger")
                  .agg(flagged=("ticket_id", "size"), wasted=("wasted", "sum"),
                       duplicates=("eng_outcome", lambda s: int((s == "Duplicate of known issue").sum())))
                  .reset_index())
    if len(by_trigger):
        by_trigger["precision"] = by_trigger["wasted"] / by_trigger["flagged"]
    base_prec = int(test["wasted_escalation"].sum()) / len(test) if len(test) else float("nan")
    link = scored[scored["action"] == ACTIONS[0]]
    is_dup = scored["eng_outcome"].eq("Duplicate of known issue")
    dup_base = float(is_dup.mean()) if len(scored) else float("nan")
    link_dup_prec = float(link["eng_outcome"].eq("Duplicate of known issue").mean()) if len(link) else float("nan")
    # p-value: chance that flagging this many tickets at random hits >= TP wasted ones.
    p_value = _binom_sf(c["TP"], c["flagged"], base_prec) if c["flagged"] else float("nan")
    return {
        "p_value_vs_baseline": p_value,
        "dup_base_rate": dup_base,
        "link_flagged": len(link),
        "link_duplicates": int(link["eng_outcome"].eq("Duplicate of known issue").sum()),
        "link_dup_precision": link_dup_prec,
        "link_dup_lift": link_dup_prec / dup_base if len(link) and dup_base else float("nan"),
        "link_dup_p_value": (_binom_sf(int(link["eng_outcome"].eq("Duplicate of known issue").sum()),
                                       len(link), dup_base) if len(link) else float("nan")),
        "thresholds": asdict(th),
        "confusion": c,
        "baseline_precision": base_prec,
        # The write-up may claim the tool beats "flag everything" only if this is True.
        "claim_supported": bool(c["flagged"] and c["precision"] > base_prec),
        "lift_vs_baseline": (c["precision"] / base_prec) if c["flagged"] else float("nan"),
        "handoffs_avoided": int(caught["eng_handoffs"].sum()),
        "proxy_hours_per_catch": per_catch,
        "proxy_hours_saved": per_catch * len(caught),
        "by_action": by_action,
        "by_trigger": by_trigger,
        "by_category": scored[scored["flagged"]].groupby("category")
                       .agg(flagged=("ticket_id", "size"), wasted=("wasted", "sum"))
                       .sort_values("flagged", ascending=False).reset_index(),
        "baselines": baselines(test),
        "scored": scored,
        "test_size": len(test),
        "test_wasted": int(test["wasted_escalation"].sum()),
    }


def walk_forward(df: pd.DataFrame, folds=FOLDS, grid: dict | None = None) -> pd.DataFrame:
    """Tune on everything before each test month, then score that month."""
    rows = []
    for train_end, test_end in folds:
        th, _ = tune(df, grid, train_end)
        esc = df[df["escalated"]]
        test = esc[(esc["created_at"] >= train_end) & (esc["created_at"] < test_end)]
        c = confusion(apply_rules(stats_table(df, test), th))
        base = float(test["wasted_escalation"].mean())
        rows.append({"test_month": train_end.strftime("%b %Y"), "escalations": len(test),
                     "baseline_precision": base} | {k: c[k] for k in
                    ("flagged", "TP", "FP", "catch_rate", "precision", "held_back_fixed")}
                    | {"beats_baseline": bool(c["flagged"] and c["precision"] > base),
                       "thresholds": {k: getattr(th, k) for k in (grid or GRID)}})
    out = pd.DataFrame(rows)
    pooled_tp, pooled_flag = out["TP"].sum(), out["flagged"].sum()
    pooled_base = (out["baseline_precision"] * out["escalations"]).sum() / out["escalations"].sum()
    out.attrs["pooled_precision"] = pooled_tp / pooled_flag if pooled_flag else float("nan")
    out.attrs["pooled_baseline"] = pooled_base
    return out


def threshold_grid(df: pd.DataFrame, table: list[dict] | None = None,
                   grid: dict | None = None) -> pd.DataFrame:
    """Test-set results for a small grid (for display; NOT used to pick thresholds)."""
    _, test = split(df)
    table = table if table is not None else stats_table(df, test)
    grid = grid or {"dup_rate": [0.25, 0.3, 0.4], "agent_wasted_rate": [0.6, 0.65, OFF],
                    "config_howto_rate": [OFF], "info_rate": [OFF], "min_live": [0],
                    "use_recent_dup": [True, False]}
    rows = []
    for combo in itertools.product(*grid.values()):
        th = replace(DEFAULT_THRESHOLDS, **dict(zip(grid.keys(), combo)))
        c = _fast_confusion(table, th)
        rows.append(dict(zip(grid.keys(), combo)) | {k: c[k] for k in
                    ("flagged", "TP", "FP", "catch_rate", "precision", "held_back_fixed")})
    return pd.DataFrame(rows)
