import pandas as pd
import pytest

from src import metrics as m


def test_monthly_volume(df):
    assert df.groupby("month").size().tolist() == [390, 462, 592]


def test_backlog_snapshots(df):
    assert m.open_backlog(df, "2026-07-31 23:59") == 30
    assert m.open_backlog(df, "2026-08-31 23:59") == 23
    assert m.open_backlog(df, "2026-09-30 23:59") == 48


def test_backlog_growth(df):
    a, b = m.open_backlog(df, "2026-07-31 23:59"), m.open_backlog(df, "2026-09-30 23:59")
    assert (b - a) / a == pytest.approx(0.60)


def test_escalation_totals(df):
    esc = df[df["escalated"]]
    assert len(esc) == 486
    assert esc["eng_outcome"].value_counts().to_dict() == {
        "Fixed": 211, "Insufficient info - returned to L1": 89, "Config issue - returned to L1": 84,
        "Duplicate of known issue": 56, "Not a bug - how-to": 24, "Not reproducible": 22}


def test_wasted_escalations(df):
    h = m.headline(df)
    assert h["wasted"] == 275
    assert h["wasted_pct"] == pytest.approx(0.566, abs=0.001)


def test_handoffs(df):
    h = m.headline(df)
    assert h["handoffs_total"] == 777
    assert h["handoffs_wasted"] == 528
    esc = df[df["escalated"]]
    assert esc["eng_handoffs"].value_counts().sort_index().tolist() == [257, 167, 62]


def test_ttr_medians(df):
    h = m.headline(df)
    assert h["med_ttr_non_esc"] == pytest.approx(12.6, abs=0.1)
    assert h["med_ttr_esc"] == pytest.approx(86.8, abs=0.1)


def test_ttr_by_handoffs(df):
    closed = df[df["status"] == "Closed"]
    med = closed.groupby("eng_handoffs")["ttr_h"].median()
    assert med.tolist() == pytest.approx([12.6, 58.6, 110.4, 169.9], abs=0.1)


def test_open_hours_share(df):
    assert m.open_hours_share(df) == pytest.approx(0.714, abs=0.001)


def test_agent_escalation_rate(df):
    a = m.by_agent(df).set_index("assigned_agent")
    assert a.loc["Karan B", "esc_pct"] == pytest.approx(0.16, abs=0.01)
    assert a.loc["Rahul T", "esc_pct"] == pytest.approx(0.62, abs=0.01)


def test_karan_reopen_non_esc(df):
    a = m.by_agent(df).set_index("assigned_agent")
    assert a.loc["Karan B", "reopen_pct_non_esc"] == pytest.approx(0.28, abs=0.01)


def test_csat_by_handoffs(df):
    c = df.groupby("eng_handoffs")["csat_score"].mean()
    assert c.round(2).tolist() == [4.01, 3.56, 2.80, 2.10]


def test_weekly_kpis_columns(df):
    w = m.weekly_kpis(df)
    for col in ["volume", "backlog", "med_ttr", "esc_pct", "wasted_pct", "reopen_pct",
                "csat", "csat_resp_rate", "p1p2_frt"]:
        assert col in w.columns
    assert w["volume"].sum() == 1444
    assert w["backlog"].iloc[-1] == 48


def test_weekly_week_count(df):
    w = m.weekly_kpis(df)
    assert len(w) == 14
    assert w["week"].iloc[0] == pd.Timestamp("2026-06-29")
    assert w["week"].iloc[-1] == pd.Timestamp("2026-09-28")


def test_empty_group(df):
    empty = df[df["assigned_agent"] == "Nobody"]
    for fn in (m.by_agent, m.by_category, m.by_template, m.weekly_kpis):
        out = fn(empty)
        assert isinstance(out, pd.DataFrame) and out.empty


def test_guardrail_baselines(df):
    h = m.headline(df)
    assert h["reopen_pct"] == pytest.approx(0.10, abs=0.01)
    assert h["csat_mean"] == pytest.approx(3.7, abs=0.01)
    assert h["csat_resp_rate"] == pytest.approx(0.45, abs=0.01)
    p = df.groupby("priority")["frt_h"].median()
    assert p["P1"] == pytest.approx(0.28, abs=0.01)
    assert p["P2"] == pytest.approx(1.05, abs=0.01)
