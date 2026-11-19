import math
from dataclasses import replace

import pytest

from src import backtest as bt
from src.rules import DEFAULT_THRESHOLDS as D


def test_split_sizes(df):
    train, test = bt.split(df)
    assert len(train) == 297
    assert len(test) == 189
    assert test["wasted_escalation"].sum() == 111
    assert test["fixed"].sum() == 78


def test_confusion_sums(df, test_table):
    c = bt.run_backtest(df, D, test_table)["confusion"]
    assert c["TP"] + c["FP"] + c["FN"] + c["TN"] == 189


def test_metric_definitions(df, test_table):
    c = bt.run_backtest(df, D, test_table)["confusion"]
    assert c["catch_rate"] == pytest.approx(c["TP"] / 111)
    assert c["precision"] == pytest.approx(c["TP"] / (c["TP"] + c["FP"]))
    assert c["held_back_fixed"] == c["FP"]


def test_deterministic(df, test_table):
    a = bt.run_backtest(df, D, test_table)
    b = bt.run_backtest(df, D)                    # rebuilds the history table
    assert a["confusion"] == b["confusion"]
    assert a["scored"].equals(b["scored"])


@pytest.mark.parametrize("hi,lo", [
    (D, replace(D, dup_rate=0.2, config_howto_rate=0.25, info_rate=0.15)),
    (replace(D, dup_rate=bt.OFF, config_howto_rate=bt.OFF, info_rate=bt.OFF, min_live=2),
     replace(D, dup_rate=0.5, config_howto_rate=0.5, info_rate=0.5, min_live=1)),
])
def test_threshold_monotonic(test_table, hi, lo):
    f_hi = bt.confusion(bt.apply_rules(test_table, hi))["flagged"]
    f_lo = bt.confusion(bt.apply_rules(test_table, lo))["flagged"]
    assert f_lo >= f_hi


def test_baseline_comparison(df, test_table, tuned):
    th, _ = tuned
    r = bt.run_backtest(df, th, test_table)
    base = r["baselines"].set_index("strategy")
    assert base.loc["Flag nothing", "TP"] == 0 and math.isnan(base.loc["Flag nothing", "precision"])
    assert base.loc["Flag everything", "precision"] == pytest.approx(111 / 189)
    assert r["baseline_precision"] == pytest.approx(0.587, abs=0.001)
    # The claim may only be made if precision actually beats the baseline.
    assert r["claim_supported"] == (r["confusion"]["precision"] > 111 / 189)


def test_thresholds_frozen(df, tuned):
    th, _ = tuned
    sep = df["created_at"] >= bt.SPLIT
    poisoned = df.copy()
    poisoned.loc[sep, "eng_outcome"] = "Duplicate of known issue"
    poisoned.loc[sep, "wasted_escalation"] = True
    poisoned.loc[sep, "escalated"] = True
    th2, _ = bt.tune(poisoned)
    th3, _ = bt.tune(df[~sep])
    assert th == th2 == th3


def test_thresholds_frozen_august_fold(df):
    cut = bt.FOLDS[0][0]
    later = df["created_at"] >= cut
    poisoned = df.copy()
    poisoned.loc[later, "eng_outcome"] = "Fixed"
    poisoned.loc[later, "wasted_escalation"] = False
    a, _ = bt.tune(df, train_end=cut)
    b, _ = bt.tune(poisoned, train_end=cut)
    assert a == b


def test_wilson_lower_bound():
    assert bt.wilson_lower(0, 0) == 0.0
    assert bt.wilson_lower(10, 10) < 1.0
    assert bt.wilson_lower(30, 40) > bt.wilson_lower(3, 4)     # same rate, more evidence
    assert bt.wilson_lower(45, 75) < 45 / 75


def test_binomial_p_value():
    assert bt._binom_sf(0, 10, 0.5) == pytest.approx(1.0)
    assert bt._binom_sf(10, 10, 0.5) == pytest.approx(0.5 ** 10)


def test_significance_fields(df, test_table, tuned):
    th, _ = tuned
    r = bt.run_backtest(df, th, test_table)
    assert 0 <= r["p_value_vs_baseline"] <= 1
    assert r["dup_base_rate"] == pytest.approx(27 / 189)
    assert r["link_duplicates"] <= r["link_flagged"]
    assert set(r["by_trigger"]["trigger"]) <= {"dup", "recent", "live", "config", "info", "agent"}


def test_walk_forward(df):
    wf = bt.walk_forward(df)
    assert wf["test_month"].tolist() == ["Aug 2026", "Sep 2026"]
    assert wf["escalations"].tolist() == [151, 189]
    assert wf["baseline_precision"].round(3).tolist() == [0.563, 0.587]
    assert (wf["TP"] + wf["FP"] == wf["flagged"]).all()
    assert "pooled_precision" in wf.attrs


def test_tuning_flags_enough(df, tuned):
    _, res = tuned
    train, _ = bt.split(df)
    assert res.iloc[0]["flagged"] >= bt.MIN_FLAG_SHARE * len(train)
