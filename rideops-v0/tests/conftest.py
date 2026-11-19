import pandas as pd
import pytest

from src import backtest as bt
from src.load import load_raw, load_tickets


@pytest.fixture(scope="session")
def df():
    """The full ticket table, loaded once per test session."""
    return load_tickets()


@pytest.fixture(scope="session")
def raw():
    return load_raw()


@pytest.fixture(scope="session")
def test_table(df):
    _, test = bt.split(df)
    return bt.stats_table(df, test)


@pytest.fixture(scope="session")
def tuned(df):
    return bt.tune(df)


def make_hist(rows, t="2026-09-15 12:00"):
    """Synthetic history for rule tests.

    Each row: dict(outcome=..., days_ago_closed=..., template=..., category=..., open=False,
    created_days_ago=...). Escalated unless outcome is None.
    """
    t = pd.Timestamp(t)
    out = []
    for i, r in enumerate(rows):
        created = t - pd.Timedelta(days=r.get("created_days_ago", r.get("days_ago_closed", 5) + 3))
        if r.get("open"):
            closed = pd.NaT
        elif "closed_at" in r:
            closed = pd.Timestamp(r["closed_at"])
        else:
            closed = t - pd.Timedelta(days=r.get("days_ago_closed", 5))
        outcome = r.get("outcome", "Fixed")
        out.append({
            "ticket_id": r.get("ticket_id", f"SUP-9{i:04d}"),
            "created_at": created,
            "final_closed_at": closed,
            "escalated": outcome is not None,
            "template": r.get("template", "Tpl A"),
            "category": r.get("category", "Cat A"),
            "eng_outcome": outcome,
            "eng_ticket_id": r.get("eng_ticket_id", f"ENG-9{i:03d}" if outcome is not None else None),
            "status": r.get("status", "Open - with Engineering" if r.get("open") else "Closed"),
            "assigned_agent": r.get("agent", "Agent A"),
        })
    return pd.DataFrame(out), t
