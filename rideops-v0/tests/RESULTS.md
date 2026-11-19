# Test results

Run: `python -m pytest -v` on 19 Nov 2026 (Python 3.12.4, Windows 11): **90 passed, 0 failed** (~75s).

| File | Tests | Covers testing-plan section |
|---|---|---|
| `test_load.py` | 18 | §2 schema, golden counts, edge cases (no first response, reopened-open tickets, open escalations with outcomes) |
| `test_metrics.py` | 16 | §3 volume, backlog snapshots 30/23/48, +60%, outcomes, handoffs 777/528, TTR medians, 71.4% open-hours share, agent rates, CSAT by handoffs, weekly columns and 14 weeks, empty groups, guardrail baselines |
| `test_templates.py` | 6 | §4 digit replacement, 201 → 48 templates, coverage, quoted commas, unknown text |
| `test_rules.py` | 26 | §5.1 every rule branch on synthetic histories (incl. inclusive 0.30 boundary, rule order, low confidence, reason text); v2 smoothing (small templates shrink toward category, large ones converge) and agent rule (fires, needs ≥ 10 escalations, can be switched off, ignores still-open escalations, template rules take priority); §5.2 leakage: no future tickets, outcome only after close, self excluded, shuffle invariance, live-at-t |
| `test_backtest.py` | 14 | §6 split 297 / 189 (111 wasted, 78 Fixed), confusion sums, metric definitions, determinism, monotonic thresholds, baselines, thresholds frozen for both folds (tuning unchanged when later rows are poisoned or removed), Wilson bound, binomial p-value, walk-forward folds |
| `test_app.py` | 10 | §7.1 AppTest smoke tests: triage lists 48 open tickets, all 3 pages render, Rahul T = 6 / Karan B = 9, manual entry, unknown text → low confidence, 14 weekly points, threshold slider changes the table |

## Backtest results (§6 "results to record")

Test set: 189 September escalations, 111 wasted, 78 Fixed, 27 duplicates. Baseline "flag everything" precision = **58.7%**.

### v2 rules (current)

Changes from v1: template outcome rates smoothed toward the category rate (and category toward team); new
agent track-record rule; tuning by the lower 95% confidence bound of precision instead of raw precision; a
walk-forward check across two months.

Tuned on Jul–Aug: duplicate rate ≥ 20%, config + how-to ≥ 40%, agent returned-unfixed ≥ 65%; insufficient-info,
live-engineering and recent-duplicate rules off. On Jul–Aug: 61 flagged, 75.4% precision (lower bound 65.4%).

| | Flagged | Caught (TP) | Catch rate | Precision | Fixed held back | Handoffs avoided |
|---|---|---|---|---|---|---|
| **v2, September** | 75 | 45 | 40.5% | **60.0%** | 30 | 75 |
| v1 tuned, September | 65 | 32 | 28.8% | 49.2% | 33 | 52 |
| Plan defaults (v2 engine) | 164 | 95 | 85.6% | 57.9% | 69 | n/a |

By the rule that fired (September):

| Rule | Flagged | Wasted | Precision | Real duplicates |
|---|---|---|---|---|
| Duplicate rate (→ Link to known issue) | 33 | 21 | 64% | **16** |
| Agent track record (→ checklist + second check) | 30 | 20 | 67% | 1 |
| Config + how-to (→ try L1 first) | 12 | 4 | 33% | 0 |

Walk-forward (thresholds re-tuned on the months before each test month):

| Test month | Escalations | Baseline | Flagged | Precision | Beats baseline |
|---|---|---|---|---|---|
| Aug 2026 (tuned on Jul) | 151 | 56.3% | 77 | 62.3% | yes |
| Sep 2026 (tuned on Jul–Aug) | 189 | 58.7% | 75 | 60.0% | yes |
| Pooled | 340 | 57.6% | 152 | 61.2% | yes |

### Verdict

1. **Wasted escalations overall: ahead of the baseline in both months, but not significant.** September 60.0% vs
   58.7% (binomial p = 0.46). `claim_supported` is True, but the margin is within noise. The write-up may say the
   rules "match or slightly beat flagging everything while sending 60% fewer tickets back"; it must **not** claim
   they reliably predict wasted escalations.
2. **Duplicate detection: strong and significant.** 16 of 33 "Link to known issue" flags were real duplicates
   (48.5%) vs a 14.3% base rate: **3.4× lift, p ≈ 3 × 10⁻⁶**. All 33 are in Report export, matching D5. This is the
   claim to lead with.
3. **The agent signal holds out of sample** (67% precision in September, 80% for the top fifth in August) and is the
   main reason v2 beats v1. It flags a pattern for the lead to coach, not a ticket property.
4. **The config rule is the weak part** (33% in September). It was chosen on Jul–Aug, so it stays in the backtest
   as-is; dropping it because of September would leak. Review it after the pilot.

Proxy saving for v2: 75 engineering handoffs avoided and ~1,693 ticket-hours (45 caught × 37.6h, the Jul–Aug gap in
median close time between wasted and Fixed escalations). Proxy only; there are no engineering effort logs.

### v1 rules (for the record)

Raw template rates, tuned by raw precision: 49.2% on September, below the baseline, so that claim was dropped.
Template-level wasted rates barely carried over between months (e.g. "Roster shows duplicate entries" 22% → 83%,
"Tracking link not opening" 91% → 33%), which is why v2 smooths them.

## Manual sanity checks (§6)

- Reason text names the triggering rate, threshold and sample size, e.g. *"Duplicate rate 58% across 12 past
  escalations of this issue (threshold 20%)"* and *"Rahul T's past escalations came back without a fix 76% of the
  time (87 escalations; team 56%, threshold 65%)"*. ✔
- All 33 "Link to known issue" recommendations fall in Report export (D5). ✔
- Live app checked after the change: Backtest page shows both verdicts; triage page shows the agent rule for
  Rahul T's queue. ✔

## Not covered by automated tests

- §7.2 manual walkthrough items that need eyes (readability in ~5s, ~1,000px layout, chart labels).
- §8 deployment: Streamlit Community Cloud link and fresh-clone check need a GitHub repo, which hasn't been created.
- §9 user acceptance: live pilot, can't be tested on historical data.
