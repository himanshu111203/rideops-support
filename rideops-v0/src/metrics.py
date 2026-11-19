"""Backlog, time-to-close, reopen and escalation KPIs.

Caveat: the data has no timestamp for a reopen, so a reopened ticket is counted as
open from creation to final close (including the gap between first close and the
reopen). That slightly overstates the backlog.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.load import CUTOFF

WEEKLY_COLUMNS = ["week", "volume", "backlog", "med_ttr", "esc_pct", "wasted_pct",
                  "reopen_pct", "csat", "csat_resp_rate", "p1p2_frt"]
GROUP_COLUMNS = ["volume", "escalations", "esc_pct", "wasted", "wasted_pct", "handoffs",
                 "reopen_pct", "reopen_pct_non_esc", "csat", "csat_resp_rate",
                 "med_ttr_closed", "med_first_close_non_esc_h", "open_now"]


# ---------------------------------------------------------------- backlog
def open_backlog(df: pd.DataFrame, t) -> int:
    """Tickets created at or before t and not finally closed by t."""
    t = pd.Timestamp(t)
    created = df["created_at"] <= t
    still_open = df["final_closed_at"].isna() | (df["final_closed_at"] > t)
    return int((created & still_open).sum())


def daily_backlog(df: pd.DataFrame) -> pd.DataFrame:
    days = pd.date_range(df["created_at"].min().normalize(), CUTOFF.normalize(), freq="D")
    snaps = [d + pd.Timedelta(hours=23, minutes=59) for d in days]
    return pd.DataFrame({"date": days, "backlog": [open_backlog(df, s) for s in snaps]})


def open_hours_share(df: pd.DataFrame) -> float:
    """Share of all open ticket-hours (created -> final close or cutoff) from escalated tickets."""
    total = df["ttr_h"].sum()
    return float(df.loc[df["escalated"], "ttr_h"].sum() / total) if total else float("nan")


# ---------------------------------------------------------------- helpers
def _rate(mask: pd.Series) -> float:
    return float(mask.mean()) if len(mask) else float("nan")


def _median(s: pd.Series) -> float:
    s = s.dropna()
    return float(s.median()) if len(s) else float("nan")


def _kpis(sub: pd.DataFrame) -> dict:
    esc = sub[sub["escalated"]]
    closed = sub[sub["status"] == "Closed"]
    non_esc = sub[~sub["escalated"]]
    first_close_h = (non_esc["first_closed_at"] - non_esc["created_at"]).dt.total_seconds() / 3600
    return {
        "volume": len(sub),
        "escalations": len(esc),
        "esc_pct": _rate(sub["escalated"]),
        "wasted": int(esc["wasted_escalation"].sum()),
        "wasted_pct": _rate(esc["wasted_escalation"]),
        "handoffs": int(sub["eng_handoffs"].sum()),
        "reopen_pct": _rate(sub["reopened"]),
        "reopen_pct_non_esc": _rate(non_esc["reopened"]),
        "csat": float(sub["csat_score"].mean()) if sub["csat_score"].notna().any() else float("nan"),
        "csat_resp_rate": _rate(sub["csat_score"].notna()),
        "med_ttr_closed": _median(closed["ttr_h"]),
        "med_first_close_non_esc_h": _median(first_close_h),
        "open_now": int(sub["is_open"].sum()),
    }


def group_kpis(df: pd.DataFrame, by: str) -> pd.DataFrame:
    rows = []
    for key, sub in df.groupby(by, sort=True):
        rows.append({by: key, **_kpis(sub)})
    return pd.DataFrame(rows, columns=[by] + GROUP_COLUMNS)


def by_agent(df: pd.DataFrame) -> pd.DataFrame:
    return group_kpis(df, "assigned_agent")


def by_category(df: pd.DataFrame) -> pd.DataFrame:
    return group_kpis(df, "category")


def by_template(df: pd.DataFrame) -> pd.DataFrame:
    out = group_kpis(df, "template")
    if len(out):
        cat = df.groupby("template")["category"].agg(lambda s: s.mode().iat[0])
        out.insert(1, "category", out["template"].map(cat))
    return out


# ---------------------------------------------------------------- weekly
def weekly_kpis(df: pd.DataFrame) -> pd.DataFrame:
    """One row per Monday-starting week, from the first ticket's week through the cutoff week.

    volume / esc / wasted / reopen / csat / P1-P2 first response: tickets *created* that week.
    backlog: open_backlog at week end (capped at the data cutoff).
    med_ttr: median time to final close of tickets *finally closed* that week.
    """
    if df.empty:
        return pd.DataFrame(columns=WEEKLY_COLUMNS)
    start = df["week"].min()
    weeks = pd.date_range(start, CUTOFF.normalize() - pd.Timedelta(days=CUTOFF.weekday()), freq="7D")
    close_week = (df["final_closed_at"].dt.normalize()
                  - pd.to_timedelta(df["final_closed_at"].dt.weekday, unit="D"))
    rows = []
    for w in weeks:
        sub = df[df["week"] == w]
        esc = sub[sub["escalated"]]
        end = min(w + pd.Timedelta(days=7) - pd.Timedelta(minutes=1), CUTOFF)
        p1p2 = sub[sub["priority"].isin(["P1", "P2"])]
        rows.append({
            "week": w,
            "volume": len(sub),
            "backlog": open_backlog(df, end),
            "med_ttr": _median(df.loc[close_week == w, "ttr_h"]),
            "esc_pct": _rate(sub["escalated"]),
            "wasted_pct": _rate(esc["wasted_escalation"]),
            "reopen_pct": _rate(sub["reopened"]),
            "csat": float(sub["csat_score"].mean()) if sub["csat_score"].notna().any() else np.nan,
            "csat_resp_rate": _rate(sub["csat_score"].notna()),
            "p1p2_frt": _median(p1p2["frt_h"]),
        })
    return pd.DataFrame(rows, columns=WEEKLY_COLUMNS)


# ---------------------------------------------------------------- headline numbers
def headline(df: pd.DataFrame) -> dict:
    closed = df[df["status"] == "Closed"]
    esc = df[df["escalated"]]
    return {
        "tickets": len(df),
        "backlog_31_jul": open_backlog(df, "2026-07-31 23:59"),
        "backlog_30_sep": open_backlog(df, "2026-09-30 23:59"),
        "escalations": len(esc),
        "fixed": int(esc["fixed"].sum()),
        "wasted": int(esc["wasted_escalation"].sum()),
        "wasted_pct": float(esc["wasted_escalation"].mean()),
        "handoffs_total": int(df["eng_handoffs"].sum()),
        "handoffs_wasted": int(esc.loc[esc["wasted_escalation"], "eng_handoffs"].sum()),
        "med_ttr_non_esc": _median(closed.loc[~closed["escalated"], "ttr_h"]),
        "med_ttr_esc": _median(closed.loc[closed["escalated"], "ttr_h"]),
        "open_hours_share_esc": open_hours_share(df),
        "reopen_pct": float(df["reopened"].mean()),
        "csat_mean": float(df["csat_score"].mean()),
        "csat_resp_rate": float(df["csat_score"].notna().mean()),
    }
