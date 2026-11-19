"""The eight diagnosis findings (D1-D8) as tables. Used by the Diagnosis page and the notebook."""
from __future__ import annotations

import pandas as pd

from src.metrics import by_agent


def d1_volume_by_category(df: pd.DataFrame) -> pd.DataFrame:
    t = df.pivot_table(index="category", columns="month", values="ticket_id", aggfunc="count", fill_value=0)
    t["growth_jul_sep"] = t["2026-09"] / t["2026-07"] - 1
    return t.sort_values("growth_jul_sep", ascending=False).reset_index()


def monthly_volume(df: pd.DataFrame) -> pd.Series:
    return df.groupby("month").size()


def d2_ttr_by_handoffs(df: pd.DataFrame) -> pd.DataFrame:
    closed = df[df["status"] == "Closed"]
    return (closed.groupby("eng_handoffs")["ttr_h"].agg(["count", "median"])
            .rename(columns={"median": "median_ttr_h"}).reset_index())


def d3_outcomes(df: pd.DataFrame) -> pd.DataFrame:
    esc = df[df["escalated"]]
    return (esc.groupby("eng_outcome").agg(tickets=("ticket_id", "size"), handoffs=("eng_handoffs", "sum"))
            .sort_values("tickets", ascending=False).reset_index())


def d4_ttr_by_outcome(df: pd.DataFrame) -> pd.DataFrame:
    closed = df[(df["status"] == "Closed") & df["escalated"]]
    return (closed.groupby("eng_outcome").agg(median_ttr_h=("ttr_h", "median"),
                                              mean_handoffs=("eng_handoffs", "mean"),
                                              tickets=("ticket_id", "size"))
            .sort_values("median_ttr_h", ascending=False).reset_index())


def d5_duplicates(df: pd.DataFrame) -> tuple[pd.Series, pd.DataFrame]:
    esc = df[df["escalated"]]
    dup = esc["eng_outcome"].eq("Duplicate of known issue")
    by_month = esc[dup].groupby("month").size()
    by_tpl = (esc.assign(dup=dup).groupby(["category", "template"])
              .agg(escalations=("ticket_id", "size"), duplicates=("dup", "sum"), dup_share=("dup", "mean"))
              .query("duplicates > 0").sort_values("duplicates", ascending=False).reset_index())
    return by_month, by_tpl


def d6_agents_priority(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    agents = by_agent(df)[["assigned_agent", "volume", "esc_pct", "wasted_pct"]].sort_values("esc_pct")
    prio = df.groupby("priority")["escalated"].mean().rename("esc_pct").reset_index()
    return agents, prio


def d7_fast_close(df: pd.DataFrame) -> pd.DataFrame:
    return by_agent(df)[["assigned_agent", "med_first_close_non_esc_h", "reopen_pct_non_esc",
                         "reopen_pct", "csat"]].sort_values("med_first_close_non_esc_h")


def d8_client_feel(df: pd.DataFrame) -> dict:
    closed = df[df["status"] == "Closed"]
    return {
        "csat_by_handoffs": df.groupby("eng_handoffs")["csat_score"].mean(),
        "csat_reopened": df.groupby("reopened")["csat_score"].mean(),
        "ttr_reopened": closed.groupby("reopened")["ttr_h"].median(),
    }
