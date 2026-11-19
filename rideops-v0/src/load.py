"""Load the RideOps ticket CSV, parse dates and add derived columns."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.templates import to_template

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
TICKETS_CSV = DATA_DIR / "rideops_support_tickets.csv"
DICTIONARY_CSV = DATA_DIR / "rideops_data_dictionary.csv"

# Data was pulled on 30 Sep 2026; open tickets are measured up to this instant.
CUTOFF = pd.Timestamp("2026-09-30 23:59")

DATE_COLS = ["created_at", "first_response_at", "first_closed_at", "final_closed_at"]

WASTED_OUTCOMES = [
    "Insufficient info - returned to L1",
    "Config issue - returned to L1",
    "Duplicate of known issue",
    "Not a bug - how-to",
    "Not reproducible",
]


def _hours(delta: pd.Series) -> pd.Series:
    return delta.dt.total_seconds() / 3600.0


def load_raw(path: str | Path | None = None) -> pd.DataFrame:
    """Read the CSV as-is (dates parsed, nothing derived)."""
    df = pd.read_csv(path or TICKETS_CSV)
    for c in DATE_COLS:
        df[c] = pd.to_datetime(df[c], format="%Y-%m-%d %H:%M")
    return df


def add_derived(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["frt_h"] = _hours(df["first_response_at"] - df["created_at"])  # NaN stays NaN
    end = df["final_closed_at"].fillna(CUTOFF)
    df["ttr_h"] = _hours(end - df["created_at"])
    df["is_open"] = df["status"] != "Closed"
    df["escalated"] = df["escalated_to_eng"].eq("Yes")
    df["fixed"] = df["eng_outcome"].eq("Fixed")
    df["wasted_escalation"] = df["escalated"] & ~df["fixed"]
    df["reopened"] = df["reopen_count"] > 0
    # Week starts Monday; label = the Monday's date.
    df["week"] = (df["created_at"].dt.normalize()
                  - pd.to_timedelta(df["created_at"].dt.weekday, unit="D"))
    df["month"] = df["created_at"].dt.to_period("M").astype(str)
    df["template"] = df["description"].map(to_template)
    return df


def run_checks(df: pd.DataFrame) -> dict[str, bool]:
    """Data checks run on every load. Returns {check_name: passed}."""
    checks = {
        "ticket_id_unique": df["ticket_id"].is_unique,
        "response_after_created": not (df["first_response_at"] < df["created_at"]).any(),
        "first_close_after_created": not (df["first_closed_at"] < df["created_at"]).any(),
        "final_close_after_first_close": not (df["final_closed_at"] < df["first_closed_at"]).any(),
        "closed_has_final_close": df.loc[df["status"] == "Closed", "final_closed_at"].notna().all(),
        "open_has_no_final_close": df.loc[df["status"] != "Closed", "final_closed_at"].isna().all(),
    }
    return {k: bool(v) for k, v in checks.items()}


def load_tickets(path: str | Path | None = None, strict: bool = True) -> pd.DataFrame:
    """Load + derive. With strict=True a failed data check raises ValueError."""
    df = add_derived(load_raw(path))
    if strict:
        failed = [k for k, ok in run_checks(df).items() if not ok]
        if failed:
            raise ValueError(f"Data checks failed: {failed}")
    return df
