"""
Reusable Streamlit UI components for StockIQ.

Every visual element that appears in more than one page lives here.
Components are pure functions: they receive data, render HTML/Streamlit
widgets, and return nothing. They never fetch data or mutate state.

Design language:
    - Dark background (#0a0e1a) with blue accent (#3b82f6)
    - DM Sans for body, JetBrains Mono for numbers and tickers
    - Colour coding: green (#10b981) = buy/positive,
                     amber (#f59e0b) = neutral/warning,
                     red (#ef4444) = sell/negative
    - Every metric has a tooltip explaining what it means
"""

from __future__ import annotations

import streamlit as st

from app.i18n import t


# ---------------------------------------------------------------------------
# Colour palette (mirrors the dark dashboard aesthetic)
# ---------------------------------------------------------------------------

_GREEN = "#10b981"
_AMBER = "#f59e0b"
_RED = "#ef4444"
_BLUE = "#3b82f6"
_MUTED = "#6b7280"


def _signal_color(signal: str) -> str:
    return {
        "buy": _GREEN, "comprar": _GREEN,
        "sell": _RED, "vender": _RED,
        "neutral": _AMBER,
    }.get(signal.lower(), _MUTED)


# ---------------------------------------------------------------------------
# Signal badge
# ---------------------------------------------------------------------------

def signal_badge(signal: str, score: float) -> None:
    """Render the composite signal badge with score.

    Args:
        signal: "buy", "neutral", or "sell".
        score: Composite score 0–100.
    """
    label_key = f"signal_{signal.lower()}"
    label = t(label_key)
    color = _signal_color(signal)

    st.markdown(
        f"""
        <div style="
            display:inline-flex;align-items:center;gap:12px;
            background:{color}18;border:1px solid {color}40;
            border-radius:8px;padding:10px 20px;margin:8px 0;
        ">
            <span style="
                width:10px;height:10px;border-radius:50%;
                background:{color};box-shadow:0 0 8px {color};
            "></span>
            <span style="
                font-family:'JetBrains Mono',monospace;
                font-size:20px;font-weight:700;color:{color};
                letter-spacing:2px;
            ">{label}</span>
            <span style="
                font-family:'JetBrains Mono',monospace;
                font-size:14px;color:{color}aa;
            ">{score:.0f}/100</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Score gauge row
# ---------------------------------------------------------------------------

def score_gauge_row(
    composite: float,
    fundamental: float,
    technical: float,
) -> None:
    """Render three score bars: fundamental, technical, composite.

    Args:
        composite: Composite score 0–100.
        fundamental: Fundamental (Shiller) score 0–100.
        technical: Technical (Murphy) score 0–100.
    """
    def _bar(label: str, value: float, color: str) -> str:
        pct = max(0, min(100, value))
        return f"""
        <div style="margin-bottom:14px;">
            <div style="display:flex;justify-content:space-between;
                        margin-bottom:5px;">
                <span style="font-size:12px;color:#9ca3af;">{label}</span>
                <span style="font-family:'JetBrains Mono',monospace;
                             font-size:12px;color:{color};font-weight:600;">
                    {value:.0f}
                </span>
            </div>
            <div style="height:6px;background:#1f2937;border-radius:3px;">
                <div style="height:100%;width:{pct}%;background:{color};
                            border-radius:3px;transition:width 0.6s ease;">
                </div>
            </div>
        </div>
        """

    st.markdown(
        _bar(t("fundamental_score"), fundamental, _BLUE)
        + _bar(t("technical_score"), technical, "#8b5cf6")
        + _bar(t("composite_score"), composite, _signal_color(
            "buy" if composite >= 60 else "sell" if composite < 40 else "neutral"
        )),
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Metric cards
# ---------------------------------------------------------------------------

def metric_card(
    label: str,
    value: str,
    delta: str | None = None,
    delta_positive: bool | None = None,
    help_text: str | None = None,
) -> None:
    """Render a styled metric card.

    Args:
        label: Metric name.
        value: Primary value to display.
        delta: Optional change indicator (e.g. "+10.5%").
        delta_positive: True → green delta, False → red, None → amber.
        help_text: Tooltip shown on hover via st.metric help.
    """
    if delta_positive is True:
        delta_color = _GREEN
    elif delta_positive is False:
        delta_color = _RED
    else:
        delta_color = _AMBER

    delta_html = ""
    if delta:
        delta_html = f"""
        <div style="font-size:12px;color:{delta_color};margin-top:4px;
                    font-family:'JetBrains Mono',monospace;">
            {delta}
        </div>
        """

    help_html = ""
    if help_text:
        help_html = f"""
        <div style="font-size:11px;color:{_MUTED};margin-top:6px;
                    line-height:1.4;">{help_text}</div>
        """

    st.markdown(
        f"""
        <div style="
            background:#111827;border:1px solid #1f2937;
            border-radius:10px;padding:16px 18px;height:100%;
        ">
            <div style="font-size:11px;color:{_MUTED};text-transform:uppercase;
                        letter-spacing:0.08em;margin-bottom:6px;">{label}</div>
            <div style="font-family:'JetBrains Mono',monospace;font-size:22px;
                        font-weight:600;color:#f9fafb;">{value}</div>
            {delta_html}{help_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Technical signal row
# ---------------------------------------------------------------------------

def signal_row(label: str, signal: str, value_str: str, note: str = "") -> None:
    """Render a single indicator row in the technical signals table.

    Args:
        label: Indicator name (e.g. "RSI (14)").
        signal: "buy", "neutral", or "sell".
        value_str: Formatted value string (e.g. "52.3 — Neutral zone").
        note: Optional short note shown in muted text.
    """
    color = _signal_color(signal)
    label_key = f"signal_{signal.lower()}"
    sig_label = t(label_key)

    note_html = ""
    if note:
        note_html = f"""
        <div style="font-size:10px;color:{_MUTED};margin-top:2px;">
            {note}
        </div>
        """

    st.markdown(
        f"""
        <div style="
            display:flex;align-items:flex-start;justify-content:space-between;
            padding:10px 0;border-bottom:1px solid #1f2937;
        ">
            <div style="font-size:13px;color:#e5e7eb;">{label}</div>
            <div style="text-align:right;">
                <div style="display:flex;align-items:center;gap:8px;">
                    <span style="font-size:12px;color:#9ca3af;
                                 font-family:'JetBrains Mono',monospace;">
                        {value_str}
                    </span>
                    <span style="
                        font-size:10px;font-weight:600;padding:2px 8px;
                        border-radius:99px;letter-spacing:0.05em;
                        background:{color}18;color:{color};
                    ">{sig_label}</span>
                </div>
                {note_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Education / explanation box
# ---------------------------------------------------------------------------

def explain_box(title: str, content: str, source: str = "") -> None:
    """Render the 'What does this mean?' educational panel.

    Args:
        title: Bold header for the explanation.
        content: Main explanation text (HTML allowed).
        source: Bibliographic reference (e.g. "Murphy (1999) p.225").
    """
    source_html = ""
    if source:
        source_html = f"""
        <div style="margin-top:10px;font-size:10px;color:{_MUTED};
                    font-style:italic;">Source: {source}</div>
        """

    st.markdown(
        f"""
        <div style="
            background:#0f172a;border:1px solid #1e3a5f;
            border-left:3px solid {_BLUE};border-radius:8px;
            padding:14px 16px;margin-top:12px;
        ">
            <div style="font-size:13px;font-weight:600;color:#93c5fd;
                        margin-bottom:8px;">{title}</div>
            <div style="font-size:12px;color:#d1d5db;line-height:1.6;">
                {content}
            </div>
            {source_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Data quality warning banner
# ---------------------------------------------------------------------------

def data_warnings(warnings: list[str]) -> None:
    """Render data quality warnings as a collapsible amber banner.

    Args:
        warnings: List of warning strings from the analysis modules.
    """
    if not warnings:
        return

    items = "".join(
        f"<div style='margin-bottom:4px;'>⚠ {w}</div>" for w in warnings
    )

    with st.expander(f"⚠ {t('section_warnings')} ({len(warnings)})", expanded=False):
        st.markdown(
            f"""
            <div style="font-size:12px;color:#fbbf24;line-height:1.6;">
                {items}
            </div>
            """,
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Disclaimer footer
# ---------------------------------------------------------------------------

def disclaimer_footer() -> None:
    """Render the always-visible disclaimer and EOD data warning."""
    st.markdown("---")
    st.markdown(
        f"""
        <div style="font-size:11px;color:{_MUTED};text-align:center;
                    line-height:1.5;padding:8px 0;">
            <strong style="color:#f59e0b;">
                {t('disclaimer_short')}
            </strong>
            &nbsp;·&nbsp;
            {t('data_eod_warning')}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Section header
# ---------------------------------------------------------------------------

def section_header(title: str, subtitle: str = "") -> None:
    """Render a styled section header with optional subtitle."""
    sub_html = ""
    if subtitle:
        sub_html = f"""
        <div style="font-size:13px;color:{_MUTED};margin-top:4px;">
            {subtitle}
        </div>
        """

    st.markdown(
        f"""
        <div style="margin:24px 0 16px;">
            <div style="font-size:18px;font-weight:600;color:#f9fafb;">
                {title}
            </div>
            {sub_html}
        </div>
        """,
        unsafe_allow_html=True,
    )
