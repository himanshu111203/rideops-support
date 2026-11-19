"""RideOps escalation check: Streamlit entry point (navigation only)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st  # noqa: E402

st.set_page_config(page_title="RideOps escalation check", page_icon=":material/support_agent:",
                   layout="wide")

nav = st.navigation({
    "Agent": [st.Page("pages/0_Agent_Triage.py", title="Escalation check",
                      icon=":material/support_agent:", default=True)],
    "Lead": [
        st.Page("pages/1_Lead_Scorecard.py", title="Weekly scorecard", icon=":material/monitoring:"),
        st.Page("pages/2_Backtest.py", title="Backtest", icon=":material/science:"),
        st.Page("pages/3_Diagnosis.py", title="Diagnosis", icon=":material/troubleshoot:"),
    ],
})
nav.run()
