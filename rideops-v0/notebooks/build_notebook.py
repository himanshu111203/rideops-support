"""Generates diagnosis.ipynb (run: python notebooks/build_notebook.py, then execute it with nbconvert)."""
from pathlib import Path

import nbformat as nbf

cells = [
    ("md", "# RideOps support: diagnosis\nEvery number in the write-up comes from this notebook. "
           "Data: `data/rideops_support_tickets.csv`, pulled 30 Sep 2026."),
    ("code", "import sys, pathlib\nsys.path.insert(0, str(pathlib.Path.cwd().parent))\n"
             "import pandas as pd\npd.set_option('display.width', 200)\n"
             "from src.load import load_tickets, run_checks\nfrom src import metrics as m, diagnosis as dg, backtest as bt\n"
             "from src.rules import DEFAULT_THRESHOLDS\ndf = load_tickets()\nrun_checks(df)"),
    ("md", "## Golden counts (section 4.2 'done when')"),
    ("code", "h = m.headline(df)\n{k: h[k] for k in ['tickets','escalations','fixed','backlog_30_sep']}"),
    ("md", "## Problem summary"),
    ("code", "h"),
    ("code", "dg.monthly_volume(df)"),
    ("md", "## D1 · Volume grew in every category"),
    ("code", "dg.d1_volume_by_category(df)"),
    ("md", "## D2 · Escalation is what makes tickets slow"),
    ("code", "dg.d2_ttr_by_handoffs(df)"),
    ("md", "## D3 · Most escalations shouldn't have gone to engineering"),
    ("code", "dg.d3_outcomes(df)"),
    ("md", "## D4 · Wasted escalations are the slowest tickets"),
    ("code", "dg.d4_ttr_by_outcome(df)"),
    ("md", "## D5 · Duplicates of known issues are growing"),
    ("code", "by_month, by_tpl = dg.d5_duplicates(df)\ndisplay(by_month)\nby_tpl.head(10)"),
    ("md", "## D6 · Escalation depends on the agent, not the ticket"),
    ("code", "agents, prio = dg.d6_agents_priority(df)\ndisplay(agents)\nprio"),
    ("md", "## D7 · Fast closing is partly fake speed"),
    ("code", "dg.d7_fast_close(df)"),
    ("md", "## D8 · Clients feel the handoffs and reopens"),
    ("code", "d8 = dg.d8_client_feel(df)\nfor k, v in d8.items():\n    print(k); display(v.round(2))"),
    ("md", "## Success-measure baselines"),
    ("code", "p = df.groupby('priority')['frt_h'].median().round(2)\n"
             "{'reopen_pct': round(h['reopen_pct'],3), 'csat_mean': round(h['csat_mean'],2), "
             "'csat_resp_rate': round(h['csat_resp_rate'],3), 'P1_frt_h': p['P1'], 'P2_frt_h': p['P2']}"),
    ("code", "m.weekly_kpis(df).round(3)"),
    ("md", "## Backtest (learn Jul–Aug, test September)"),
    ("code", "th, tune_res = bt.tune(df)\n_, test = bt.split(df)\ntable = bt.stats_table(df, test)\n"
             "for name, t in [('tuned', th), ('plan defaults', DEFAULT_THRESHOLDS)]:\n"
             "    r = bt.run_backtest(df, t, table)\n"
             "    print(name, t)\n"
             "    print({k: round(v, 3) if isinstance(v, float) else v for k, v in r['confusion'].items()})\n"
             "    print('baseline precision', round(r['baseline_precision'], 3), '| claim supported:', r['claim_supported'],\n"
             "          '| handoffs avoided', r['handoffs_avoided'], '| proxy hours', round(r['proxy_hours_saved']))\n"
             "    display(r['by_action'])"),
    ("code", "r = bt.run_backtest(df, th, table)\n"
             "{k: r[k] for k in ['p_value_vs_baseline', 'dup_base_rate', 'link_flagged', 'link_duplicates',\n"
             "                   'link_dup_precision', 'link_dup_lift', 'link_dup_p_value', 'handoffs_avoided',\n"
             "                   'proxy_hours_saved']}"),
    ("code", "r['by_trigger']"),
    ("code", "r['baselines']"),
    ("md", "## Walk-forward validation (tune on prior months, test the next)"),
    ("code", "wf = bt.walk_forward(df)\ndisplay(wf)\nwf.attrs"),
    ("code", "bt.threshold_grid(df, table)"),
]

nb = nbf.v4.new_notebook()
nb["cells"] = [nbf.v4.new_markdown_cell(s) if k == "md" else nbf.v4.new_code_cell(s) for k, s in cells]
out = Path(__file__).parent / "diagnosis.ipynb"
nbf.write(nb, out)
print("wrote", out)
