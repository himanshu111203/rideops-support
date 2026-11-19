# RideOps Support Intelligence & Escalation System

An end-to-end data engineering and triage decision system built for support operations. It helps L1 support agents decide at the moment of escalation whether a ticket should go to engineering, be linked to a known issue, or be handled at L1, eliminating wasted engineering handoffs and backlog bottlenecks.

---

## 📌 Project Overview

- **Problem:** Support ticket backlog grew +60% over 3 months, with 34% of volume being escalated to engineering, consuming 71% of all open ticket hours. Crucially, **57% of escalations returned without an engineering fix** (wasted handoffs).
- **Solution:** A deterministic, leak-free rules engine extracting support templates, computing smoothed historical rates, and surfacing recommendations in real-time.
- **Application:** A Swiss-style minimalist Streamlit app with an Agent Triage screen, Weekly Lead Scorecard, Historical Backtesting interface, and Diagnostic explorer.
- **Validation:** 92 comprehensive unit, metric, leakage, and smoke tests verifying zero future-leakage, edge cases, and deterministic walk-forward performance.

---

## 📂 Repository Structure

```text
├── rideops_data_dictionary.csv           # Schema definition of support ticket attributes
├── rideops_support_tickets.csv           # Base dataset (1,444 tickets, Jul-Sep 2026)
├── .gitignore                            # Standard Python & OS ignore patterns
└── rideops-v0/                           # Core Streamlit application & logic
    ├── app.py                            # Streamlit entry point and routing
    ├── requirements.txt                  # Python dependencies
    ├── pytest.ini                        # Test runner configuration
    ├── .streamlit/                       # Custom theme & UI styling configuration
    ├── data/                             # Application ticket datasets
    ├── notebooks/                        # Diagnostic reproducible notebook & generator
    ├── pages/                            # Multi-page views
    │   ├── 0_Agent_Triage.py             # Real-time L1 escalation assistant
    │   ├── 1_Lead_Scorecard.py           # Team & agent KPI scorecard
    │   ├── 2_Backtest.py                 # Backtest results & walk-forward metrics
    │   └── 3_Diagnosis.py                # Deep-dive analytics into backlog drivers
    ├── src/                              # Core engine
    │   ├── backtest.py                   # Walk-forward backtesting engine
    │   ├── checklists.py                 # Category-specific troubleshooting checklists
    │   ├── diagnosis.py                  # D1-D8 diagnostic calculations
    │   ├── load.py                       # Data parsing & derived metrics
    │   ├── metrics.py                    # Backlog snapshots, SLA & KPI tracking
    │   ├── rules.py                      # Historical rule engine (zero temporal leakage)
    │   ├── templates.py                  # Ticket text template canonicalization
    │   └── ui.py                         # Design system & visual components
    └── tests/                            # Test suite (92 tests covering all modules)
        ├── conftest.py
        ├── RESULTS.md                    # Detailed backtest performance benchmarks
        ├── test_app.py
        ├── test_backtest.py
        ├── test_load.py
        ├── test_metrics.py
        ├── test_rules.py
        └── test_templates.py
```

---

## 🚀 Quickstart

### Prerequisites
- Python 3.10+
- Git

### Installation & Run

1. **Clone the repository:**
   ```bash
   git clone https://github.com/himanshu111203/rideops-support.git
   cd rideops-support/rideops-v0
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Launch the Streamlit app:**
   ```bash
   streamlit run app.py
   ```
   Open [http://localhost:8501](http://localhost:8501) in your browser.

4. **Run the test suite:**
   ```bash
   python -m pytest
   ```

---

## 📊 Key Highlights & Results

- **Duplicate Detection:** Successfully detected duplicates with **48% precision** vs a **14% base rate** (3.4× lift, $p \approx 3 \times 10^{-6}$), predominantly in report exports.
- **Agent Track Record Signal:** Identifies variance in escalation tendencies (from 16% to 62%) with 67% precision in identifying tickets needing guidance.
- **Zero Temporal Leakage:** Rules strictly use only past ticket history up to timestamp $t$ and closed outcomes available prior to $t$.
