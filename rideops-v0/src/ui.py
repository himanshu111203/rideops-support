"""Cached data access plus the shared design system for every Streamlit page.

Design system (from the ui-ux-pro-max skill): Minimalism & Swiss style, light-first,
dashboard density (8-32px spacing), trust-blue primary, orange accent for the driver
metric, Fira Sans for text and Fira Code for numbers/IDs, SVG icons (no emoji),
visible focus states, reduced-motion respected.
"""
from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from src import backtest as bt
from src.load import load_tickets
from src.rules import ESCALATE, ESCALATE_CHECKLIST, LINK, RESOLVE_L1

# ------------------------------------------------------------------ tokens
C = {
    "primary": "#2563EB", "primary_ink": "#1D4ED8", "primary_tint": "#EFF6FF",
    "accent": "#EA580C", "accent_tint": "#FFF7ED",
    "bg": "#F8FAFC", "card": "#FFFFFF", "fg": "#1E293B", "muted": "#E9EFF8",
    "muted_fg": "#475569", "border": "#E2E8F0",
    "good": "#15803D", "good_tint": "#F0FDF4",
    "warn": "#B45309", "warn_tint": "#FFFBEB",
    "bad": "#DC2626", "bad_tint": "#FEF2F2",
    "guard": "#0F766E",
}
# Chart series, fixed order: primary, accent, guardrail teal, slate.
SERIES = [C["primary"], C["accent"], C["guard"], "#64748B", "#7C3AED", "#DB2777", "#CA8A04", "#0891B2"]
GRID_COLOR = "#E2E8F0"

# Lucide icons (MIT), inline SVG paths.
_ICONS = {
    "link": '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>'
            '<path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
    "wrench": '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 '
              '7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>',
    "clipboard": '<rect width="8" height="4" x="8" y="2" rx="1" ry="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 '
                 '0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><path d="m9 14 2 2 4-4"/>',
    "arrow": '<path d="M7 7h10v10"/><path d="M7 17 17 7"/>',
    "alert": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>'
             '<path d="M12 9v4"/><path d="M12 17h.01"/>',
    "check": '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    "x": '<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/>',
    "user": '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
}


def icon(name: str, size: int = 18, color: str = "currentColor") -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" '
            f'fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
            f'aria-hidden="true" focusable="false">{_ICONS[name]}</svg>')


# action -> (tone, icon, short label)
ACTION_STYLE = {
    LINK: ("info", "link", "Known issue"),
    RESOLVE_L1: ("warn", "wrench", "Resolve at L1"),
    ESCALATE_CHECKLIST: ("warn", "clipboard", "Checklist first"),
    ESCALATE: ("good", "arrow", "Escalate"),
}
TONE = {
    "info": (C["primary_ink"], C["primary_tint"], C["primary"]),
    "warn": (C["warn"], C["warn_tint"], "#F59E0B"),
    "good": (C["good"], C["good_tint"], "#22C55E"),
    "bad": (C["bad"], C["bad_tint"], C["bad"]),
    "neutral": (C["muted_fg"], C["muted"], C["border"]),
}

CSS = f"""
<style>
:root {{
  --rc-primary:{C['primary']}; --rc-fg:{C['fg']}; --rc-muted-fg:{C['muted_fg']};
  --rc-border:{C['border']}; --rc-card:{C['card']}; --rc-muted:{C['muted']};
}}
.block-container {{ padding-top: 2rem; padding-bottom: 3rem; max-width: 1280px; }}
h1, h2, h3 {{ letter-spacing: -0.01em; color: var(--rc-fg); }}
h1 {{ font-weight: 700 !important; }}
h2 {{ font-weight: 600 !important; font-size: 1.25rem !important; margin-top: 0.75rem !important; }}
h3 {{ font-weight: 600 !important; font-size: 1.05rem !important; }}
p, li {{ line-height: 1.6; }}
code, .rc-mono {{ font-family: 'Fira Code', ui-monospace, monospace; font-variant-numeric: tabular-nums; }}

/* page header */
.rc-eyebrow {{ font-size: .75rem; font-weight: 600; text-transform: uppercase; letter-spacing: .08em;
  color: var(--rc-primary); margin: 0 0 .25rem; }}
.rc-title {{ font-size: 1.75rem; font-weight: 700; color: var(--rc-fg); margin: 0; line-height: 1.25; }}
.rc-sub {{ color: var(--rc-muted-fg); margin: .35rem 0 1.25rem; max-width: 72ch; font-size: .95rem; }}

/* KPI tiles */
.rc-kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(132px, 1fr)); gap: 12px; margin: 0 0 16px; }}
.rc-kpi {{ background: var(--rc-card); border: 1px solid var(--rc-border); border-radius: 10px; padding: 14px 16px; }}
.rc-kpi-label {{ font-size: .78rem; color: var(--rc-muted-fg); font-weight: 500; margin: 0 0 4px; }}
.rc-kpi-value {{ font-family: 'Fira Code', ui-monospace, monospace; font-variant-numeric: tabular-nums;
  font-size: 1.6rem; font-weight: 600; color: var(--rc-fg); line-height: 1.2; white-space: nowrap; }}
.rc-kpi-sub {{ font-size: .78rem; color: var(--rc-muted-fg); margin-top: 4px; }}
.rc-kpi[data-tone="bad"] {{ border-left: 3px solid {C['bad']}; }}
.rc-kpi[data-tone="warn"] {{ border-left: 3px solid #F59E0B; }}
.rc-kpi[data-tone="good"] {{ border-left: 3px solid #22C55E; }}
.rc-kpi[data-tone="accent"] {{ border-left: 3px solid {C['accent']}; }}

/* recommendation / callout cards */
.rc-card {{ border: 1px solid var(--rc-border); border-left-width: 4px; border-radius: 10px;
  padding: 16px 18px; margin: 4px 0 16px; background: var(--rc-card); }}
.rc-card-head {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }}
.rc-card-title {{ font-size: 1.15rem; font-weight: 600; margin: 0; color: var(--rc-fg); }}
.rc-card-body {{ margin: 8px 0 0; color: var(--rc-fg); font-size: .95rem; line-height: 1.6; }}
.rc-icon-wrap {{ display: inline-flex; width: 32px; height: 32px; border-radius: 8px; align-items: center;
  justify-content: center; flex: none; }}

/* badges */
.rc-badge {{ display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px; border-radius: 999px;
  font-size: .75rem; font-weight: 600; white-space: nowrap; border: 1px solid transparent; }}
.rc-meta {{ display: flex; flex-wrap: wrap; gap: 6px 18px; color: var(--rc-muted-fg); font-size: .88rem;
  margin: 2px 0 14px; }}
.rc-meta b {{ color: var(--rc-fg); font-weight: 600; }}
.rc-ids {{ display: flex; flex-wrap: wrap; gap: 6px; margin: 6px 0 2px; }}
.rc-id {{ font-family: 'Fira Code', ui-monospace, monospace; font-size: .82rem; padding: 2px 8px;
  border-radius: 6px; background: {C['primary_tint']}; color: {C['primary_ink']}; border: 1px solid #BFDBFE; }}
.rc-note {{ font-size: .8rem; color: var(--rc-muted-fg); display: flex; gap: 6px; align-items: flex-start; }}
.rc-section {{ font-size: .8rem; font-weight: 600; text-transform: uppercase; letter-spacing: .06em;
  color: var(--rc-muted-fg); margin: 18px 0 6px; }}

/* interaction: pointer, hover, visible focus */
button, [role="tab"], [data-baseweb="select"], label[data-baseweb="checkbox"], [role="radio"] {{ cursor: pointer; }}
button, [role="tab"] {{ transition: background-color .2s ease, border-color .2s ease, color .2s ease; }}
:focus-visible {{ outline: 2px solid var(--rc-primary) !important; outline-offset: 2px; }}
@media (prefers-reduced-motion: reduce) {{ * {{ transition: none !important; animation: none !important; }} }}

/* streamlit chrome */
[data-testid="stSidebarNav"] a span {{ font-weight: 500; }}
[data-testid="stExpander"] details {{ border-radius: 10px; }}
[data-testid="stDataFrame"] {{ border: 1px solid var(--rc-border); border-radius: 8px; }}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def _e(s) -> str:
    return html.escape(str(s))


def page_header(eyebrow: str, title: str, subtitle: str = "") -> None:
    sub = f'<p class="rc-sub">{subtitle}</p>' if subtitle else ""
    st.markdown(f'<p class="rc-eyebrow">{_e(eyebrow)}</p><h1 class="rc-title">{_e(title)}</h1>{sub}',
                unsafe_allow_html=True)


def kpi_row(items: list[dict]) -> None:
    """items: dicts with label, value, optional sub and tone (bad/warn/good/accent)."""
    cells = []
    for it in items:
        tone = f' data-tone="{it["tone"]}"' if it.get("tone") else ""
        sub = f'<div class="rc-kpi-sub">{_e(it["sub"])}</div>' if it.get("sub") else ""
        cells.append(f'<div class="rc-kpi"{tone}><div class="rc-kpi-label">{_e(it["label"])}</div>'
                     f'<div class="rc-kpi-value">{_e(it["value"])}</div>{sub}</div>')
    st.markdown(f'<div class="rc-kpis">{"".join(cells)}</div>', unsafe_allow_html=True)


def badge(text: str, tone: str = "neutral", icon_name: str | None = None) -> str:
    fg, bg, bd = TONE[tone]
    ic = icon(icon_name, 13, fg) if icon_name else ""
    return (f'<span class="rc-badge" style="color:{fg};background:{bg};border-color:{bd}33">'
            f'{ic}{_e(text)}</span>')


def callout(tone: str, icon_name: str, title: str, body: str, badges: str = "") -> None:
    """Card with a coloured left edge, icon, title and body. `body` may contain safe HTML."""
    fg, bg, bd = TONE[tone]
    st.markdown(
        f'<div class="rc-card" role="status" style="border-left-color:{bd}">'
        f'<div class="rc-card-head"><span class="rc-icon-wrap" style="background:{bg}">'
        f'{icon(icon_name, 18, fg)}</span><p class="rc-card-title">{_e(title)}</p>{badges}</div>'
        f'<p class="rc-card-body">{body}</p></div>',
        unsafe_allow_html=True)


def rec_card(rec) -> None:
    tone, ic, _ = ACTION_STYLE[rec.action]
    badges = badge("Low confidence: category-level history", "neutral", "alert") if rec.low_confidence else ""
    callout(tone, ic, rec.action, _e(rec.reason), badges)


def section(label: str) -> None:
    st.markdown(f'<p class="rc-section">{_e(label)}</p>', unsafe_allow_html=True)


def id_chips(ids: list[str]) -> None:
    st.markdown('<div class="rc-ids">' + "".join(f'<span class="rc-id">{_e(i)}</span>' for i in ids)
                + "</div>", unsafe_allow_html=True)


def note(text: str) -> None:
    st.markdown(f'<p class="rc-note">{icon("info", 14)}<span>{_e(text)}</span></p>', unsafe_allow_html=True)


# ------------------------------------------------------------------ data (cached)
@st.cache_data(show_spinner="Loading tickets…")
def get_df() -> pd.DataFrame:
    return load_tickets()


@st.cache_resource(show_spinner="Tuning thresholds on Jul–Aug…")
def get_tuned():
    return bt.tune(get_df())


@st.cache_resource(show_spinner="Running walk-forward validation (Aug and Sep)…")
def get_walk_forward():
    return bt.walk_forward(get_df())


@st.cache_resource(show_spinner="Building September history…")
def get_test_table():
    df = get_df()
    _, test = bt.split(df)
    return bt.stats_table(df, test)


# ------------------------------------------------------------------ charts
def style_fig(fig, y_title: str, x_title: str = "Week starting", height: int = 280):
    fig.update_layout(height=height, margin=dict(l=8, r=8, t=44, b=8),
                      plot_bgcolor=C["card"], paper_bgcolor=C["card"],
                      font=dict(family="Fira Sans, sans-serif", size=12, color=C["muted_fg"]),
                      title=dict(font=dict(size=14, color=C["fg"], family="Fira Sans, sans-serif"),
                                 x=0.01, xanchor="left"),
                      hovermode="x unified",
                      hoverlabel=dict(font=dict(family="Fira Code, monospace", size=12)),
                      legend=dict(orientation="h", y=-0.25))
    fig.update_xaxes(title=x_title, showgrid=False, linecolor=C["border"], tickcolor=C["border"])
    fig.update_yaxes(title=y_title, gridcolor=GRID_COLOR, zeroline=False, linecolor=C["border"])
    fig.update_traces(line=dict(width=2), selector=dict(type="scatter"))
    return fig


def pct(x) -> str:
    return "–" if pd.isna(x) else f"{x:.0%}"
