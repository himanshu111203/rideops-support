from src.templates import UNKNOWN, match_template, to_template


def test_digit_replacement():
    assert (to_template("Roster uploaded via Excel but 34 employees missing")
            == "Roster uploaded via Excel but N employees missing")


def test_multi_number():
    assert to_template("Cab arrived 25 mins late for 6 AM shift") == "Cab arrived N mins late for N AM shift"


def test_template_count(df):
    assert df["description"].nunique() == 201
    assert df["template"].nunique() == 48


def test_full_coverage(df):
    assert df["template"].notna().all()
    assert (df["template"].str.len() > 0).all()
    assert (df["template"] != UNKNOWN).all()


def test_quoted_commas(raw):
    s = "Cab did not turn up, employee took own transport"
    assert (raw["description"] == s).sum() > 0
    assert raw.shape[1] == 20


def test_unseen_description(df):
    known = set(df["template"])
    assert match_template("Something entirely new about drones", known) == UNKNOWN
    assert match_template("roster uploaded via excel but 7 employees missing", known) == \
        "Roster uploaded via Excel but N employees missing"
    assert to_template("") == UNKNOWN
