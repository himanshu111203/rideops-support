import pandas as pd

from src.load import DICTIONARY_CSV, run_checks


def test_shape(raw):
    assert raw.shape == (1444, 20)


def test_columns_match_dictionary(raw):
    d = pd.read_csv(DICTIONARY_CSV)
    expected = []
    for c in d["column"]:
        expected += [p.strip() for p in c.split("/")]
    assert list(raw.columns) == expected


def test_ticket_id_unique(raw):
    assert raw["ticket_id"].duplicated().sum() == 0


def test_eng_ticket_id_unique(raw):
    e = raw["eng_ticket_id"].dropna()
    assert len(e) == 486 and e.duplicated().sum() == 0


def test_date_range(raw):
    assert raw["created_at"].min() == pd.Timestamp("2026-07-02 01:27")
    assert raw["created_at"].max() == pd.Timestamp("2026-09-30 23:53")


def test_time_order(raw):
    assert (raw["first_response_at"] < raw["created_at"]).sum() == 0
    assert (raw["first_closed_at"] < raw["created_at"]).sum() == 0
    assert (raw["final_closed_at"] < raw["first_closed_at"]).sum() == 0


def test_null_counts(raw):
    n = raw.isna().sum()
    assert n["first_response_at"] == 5
    assert n["first_closed_at"] == 42
    assert n["final_closed_at"] == 48
    assert n["eng_ticket_id"] == 958 and n["eng_outcome"] == 958
    assert n["csat_score"] == 796


def test_status_counts(raw):
    assert raw["status"].value_counts().to_dict() == {
        "Closed": 1396, "Open - with L1": 29, "Open - with Engineering": 19}


def test_closed_has_final_close(raw):
    closed = raw["status"] == "Closed"
    assert raw.loc[closed, "final_closed_at"].notna().all()
    assert raw.loc[~closed, "final_closed_at"].isna().all()


def test_escalation_consistency(raw):
    no = raw["escalated_to_eng"] == "No"
    zero = raw["eng_handoffs"] == 0
    null = raw["eng_outcome"].isna()
    assert (no == zero).all() and (zero == null).all()
    assert no.sum() == 958


def test_enums(raw):
    assert raw["channel"].nunique() == 4
    assert raw["client_tier"].nunique() == 3
    assert raw["category"].nunique() == 10
    assert set(raw["priority"]) == {"P1", "P2", "P3", "P4"}
    assert raw["assigned_agent"].nunique() == 8
    assert raw["eng_outcome"].nunique() == 6


def test_csat_range(raw):
    assert set(raw["csat_score"].dropna().astype(int)) <= {1, 2, 3, 4, 5}


def test_reopen_dist(raw):
    assert raw["reopen_count"].value_counts().sort_index().tolist() == [1293, 135, 14, 2]


def test_data_checks_pass(df):
    assert all(run_checks(df).values())


# ---------------------------------------------------------------- edge cases
def test_missing_first_response_stays_empty(df):
    nofrt = df[df["first_response_at"].isna()]
    assert len(nofrt) == 5
    assert nofrt["is_open"].all()
    assert (nofrt["created_at"].dt.date == pd.Timestamp("2026-09-30").date()).all()
    assert set(nofrt["priority"]) <= {"P3", "P4"}
    assert nofrt["frt_h"].isna().all()           # must not become 0


def test_reopened_open_tickets_count_as_open(df):
    ids = {"SUP-11267", "SUP-11278", "SUP-11296", "SUP-11416", "SUP-11422", "SUP-11424"}
    sub = df[df["is_open"] & df["first_closed_at"].notna()]
    assert set(sub["ticket_id"]) == ids
    assert sub["is_open"].all() and sub["final_closed_at"].isna().all()


def test_open_escalated_already_have_outcome(df):
    sub = df[df["is_open"] & df["escalated"]]
    assert len(sub) == 34 and sub["eng_outcome"].notna().all()


def test_derived_columns(df):
    assert df["escalated"].sum() == 486
    assert df["wasted_escalation"].sum() == 275
    assert (df["ttr_h"] >= 0).all()
    assert (df["frt_h"].dropna() >= 0).all()
