"""Turn a free-text description into a template: every run of digits becomes N.

"Roster uploaded via Excel but 34 employees missing"
    -> "Roster uploaded via Excel but N employees missing"
"""
from __future__ import annotations

import re

import pandas as pd

UNKNOWN = "unknown_template"
_DIGITS = re.compile(r"\d+")
_SPACES = re.compile(r"\s+")


def to_template(description: str) -> str:
    if description is None or (isinstance(description, float) and pd.isna(description)):
        return UNKNOWN
    text = _SPACES.sub(" ", str(description)).strip()
    if not text:
        return UNKNOWN
    return _DIGITS.sub("N", text)


def match_template(description: str, known: set[str]) -> str:
    """Template for typed text, or UNKNOWN if it isn't one we have history for.

    Matching is case-insensitive so a hand-typed variant still lands on its template.
    """
    tpl = to_template(description)
    if tpl in known:
        return tpl
    lower = {k.lower(): k for k in known}
    return lower.get(tpl.lower(), UNKNOWN)
