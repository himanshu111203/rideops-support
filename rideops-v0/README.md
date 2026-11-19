# RideOps v0: escalation check

**What it is.** A Streamlit app that helps an L1 support agent decide, at the moment of escalation, whether a
ticket should go to engineering, be linked to a known issue, or be tried at L1 first, based on how similar tickets
went before. A second page gives the support lead a weekly scorecard.

**Who it's for.** L1 agents (triage page) and the support lead (scorecard, backtest, diagnosis).

## Run it

```bash
pip install -r requirements.txt
streamlit run app.py
python -m pytest            # 90 tests, ~75s
```

Pages (navigation in `app.py`): **Escalation check** for agents (`pages/0_Agent_Triage.py`); **Weekly
scorecard**, **Backtest** and **Diagnosis** (D1–D8, the demo opener) for the lead. Run from inside `rideops-v0` so
`.streamlit/config.toml` (theme) is picked up.

**Design system** (generated with the ui-ux-pro-max skill, in `src/ui.py` and `.streamlit/config.toml`): Minimalism &
Swiss style, light-first, dashboard density; trust blue `#2563EB` primary, orange `#EA580C` for the driver metric,
teal for guardrails; Fira Sans text with Fira Code for numbers and IDs; Lucide SVG icons (no emoji); visible focus
rings and `prefers-reduced-motion` respected.
`notebooks/diagnosis.ipynb` reproduces every number; regenerate with `python notebooks/build_notebook.py` then
`jupyter nbconvert --to notebook --execute --inplace notebooks/diagnosis.ipynb`.

## How it works

- `src/load.py`: parses dates; derives `frt_h`, `ttr_h` (to final close, or the 30 Sep 23:59 cutoff if open),
  `escalated`, `wasted_escalation` (escalated and not Fixed), `reopened`, `week`, `month`, `template`. Data checks run
  on load.
- `src/templates.py`: description → template by replacing digits with `N` (201 descriptions → 48 templates).
- `src/metrics.py`: backlog snapshots, weekly KPIs, per agent / category / template tables.
- `src/rules.py`: for a ticket at time *t*, uses only history available at *t* (tickets created before *t*;
  outcomes only of tickets finally closed before *t*; "open with engineering" judged at *t*, never from `status`).
  Template rates are smoothed toward the category rate, and the category toward the team rate.
  Decision order: link to known issue (duplicate rate / recent duplicate / live engineering ticket) → try L1 first
  (config + how-to rate) → escalate with checklist (insufficient-info rate, or the agent's own escalations come back
  unfixed too often) → escalate. Fewer than 5 past escalations of the template → category-level stats, marked low
  confidence.
- `src/backtest.py`: thresholds tuned on Jul–Aug only (by the lower 95% confidence bound of precision), tested on
  the 189 September escalations against "flag nothing" and "flag everything", with p-values and a walk-forward
  check (tune on Jul → test Aug; tune on Jul–Aug → test Sep).

## Backtest result (read this before the demo)

v2 rules (smoothed template rates + agent track record), tuned on Jul–Aug and tested on September:

- **Duplicate detection works:** 16 of 33 "Link to known issue" flags were real duplicates, 48% vs a 14% base
  rate (3.4×, p ≈ 3 × 10⁻⁶), all in Report export. Lead with this.
- **Wasted escalations overall:** 60.0% precision vs 58.7% for "flag everything", ahead in both walk-forward months
  (Aug 62.3% vs 56.3%) but not statistically significant (p = 0.46). Don't claim the tool reliably predicts
  wasted escalations.
- **Agent track record** is the most stable signal (67% precision in September).

v1 (raw template rates) scored 49%, below the baseline. Full numbers: `tests/RESULTS.md`. Pilot it as advice,
not an automatic gate.

## Assumptions

- Checklists per category (`src/checklists.py`) are assumptions, not from the data; the app labels them.
- The triage page evaluates open tickets as of the data pull (30 Sep 2026 23:59).
- Whether a past ticket was escalated is read from the final data (no escalation timestamp exists).

## Limits

- No timestamps for when a ticket went to engineering or came back, so L1 vs engineering wait can't be split.
- No SLA targets in the data.
- 55% of tickets have no CSAT score; treat CSAT as directional.
- Backlog counts a reopened ticket as open from creation to final close (no reopen timestamp), slightly overstating it.
- Savings are proxies (handoffs avoided, close-time gap); there are no engineering effort logs.
