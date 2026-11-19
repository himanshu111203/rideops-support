from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from src import metrics as m

TIMEOUT = 120


ROOT = Path(__file__).resolve().parent.parent


def run(path):
    at = AppTest.from_file(str(ROOT / path), default_timeout=TIMEOUT)
    at.run()
    assert not at.exception, at.exception
    return at


def card_text(at):
    """Text of alert boxes and custom HTML cards (rendered through st.markdown)."""
    parts = [e.value for kind in ("info", "success", "warning", "error") for e in getattr(at, kind)]
    parts += [e.value for e in at.markdown if "rc-card" in e.value]
    return " ".join(parts)


def test_triage_loads():
    at = run("app.py")
    assert len(at.selectbox(key="ticket").options) == 48


@pytest.mark.parametrize("path", ["pages/0_Agent_Triage.py", "pages/1_Lead_Scorecard.py", "pages/2_Backtest.py",
                                  "pages/3_Diagnosis.py"])
def test_each_page_loads(path):
    run(path)


@pytest.mark.parametrize("agent,n", [("Rahul T", 6), ("Karan B", 9)])
def test_agent_filter(agent, n):
    at = run("app.py")
    at.selectbox(key="agent").set_value(agent).run()
    assert not at.exception
    assert len(at.selectbox(key="ticket").options) == n


def test_manual_entry():
    at = run("app.py")
    at.radio(key="mode").set_value("Enter manually").run()
    at.selectbox(key="manual_category").set_value("Roster / booking not syncing").run()
    at.text_input(key="manual_text").input("Roster uploaded via Excel but 12 employees missing").run()
    assert not at.exception
    text = card_text(at)
    assert any(a in text for a in ["Link to known issue", "Try resolving at L1 first",
                                   "Escalate only with the checklist completed", "Escalate"])


def test_unknown_text():
    at = run("app.py")
    at.radio(key="mode").set_value("Enter manually").run()
    at.text_input(key="manual_text").input("Drone delivery hovering over the office").run()
    assert not at.exception
    assert "Low confidence" in card_text(at)


def test_no_emoji_icons():
    """Design-system rule: SVG icons, not emoji."""
    import re
    emoji = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
    for path in ["app.py", "pages/0_Agent_Triage.py", "pages/1_Lead_Scorecard.py", "pages/2_Backtest.py",
                 "pages/3_Diagnosis.py", "src/ui.py"]:
        assert not emoji.search((ROOT / path).read_text(encoding="utf-8")), path


def test_scorecard_week_count(df):
    w = m.weekly_kpis(df)
    assert len(w) == 14
    assert str(w["week"].iloc[0].date()) == "2026-06-29"
    assert str(w["week"].iloc[-1].date()) == "2026-09-28"
    run("pages/1_Lead_Scorecard.py")


def _slider_df(at):
    for d in at.dataframe:
        v = d.value
        if "FN" in v.columns and "strategy" not in v.columns and len(v) == 1:
            return v
    raise AssertionError("slider results table not found")


def test_threshold_slider():
    at = run("pages/2_Backtest.py")
    before = _slider_df(at).copy()
    at.select_slider(key="dup").set_value(0.1).run()
    at.select_slider(key="cfg").set_value(0.1).run()
    at.select_slider(key="info").set_value(0.1).run()
    assert not at.exception
    after = _slider_df(at)
    assert not before.equals(after)
