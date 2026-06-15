"""Overview page — the first screen after running an analysis."""

from __future__ import annotations

import streamlit as st

from app.components import (
    data_warnings,
    explain_box,
    metric_card,
    score_gauge_row,
    section_header,
    signal_badge,
)
from app.i18n import t


def render(result, info: dict | None, df_ind) -> None:
    if result is None:
        st.markdown(
            f"""
            <div style="text-align:center;padding:80px 20px;color:#4b5563;">
                <div style="font-size:48px;margin-bottom:16px;">📈</div>
                <div style="font-size:16px;">{t('no_ticker_prompt')}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    # ── Header ────────────────────────────────────────────────────────────
    col_title, col_badge = st.columns([2, 1])
    with col_title:
        name = (info or {}).get("longName") or (info or {}).get("shortName") or result.ticker
        currency = (info or {}).get("currency", "")
        exchange = (info or {}).get("exchange", "")
        st.markdown(
            f"""
            <div style="margin-bottom:4px;">
                <span style="font-family:'JetBrains Mono',monospace;
                             font-size:28px;font-weight:700;color:#f9fafb;">
                    {result.ticker}
                </span>
                <span style="font-size:13px;color:#6b7280;margin-left:10px;">
                    {name}
                </span>
            </div>
            <div style="font-size:11px;color:#4b5563;">
                {exchange} · {currency} ·
                <span style="color:#6b7280;">{t('analysed_at')}: {result.analysed_at[:10]}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_badge:
        signal_badge(result.signal, result.composite_score)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── Score gauges ──────────────────────────────────────────────────────
    score_gauge_row(
        composite=result.composite_score,
        fundamental=result.score_breakdown["fundamental"],
        technical=result.score_breakdown["technical"],
    )

    # ── Confidence ────────────────────────────────────────────────────────
    conf_key = f"confidence_{result.confidence}"
    conf_label = t(conf_key)
    conf_color = {"high": "#10b981", "medium": "#f59e0b", "low": "#ef4444"}.get(
        result.confidence, "#6b7280"
    )
    st.markdown(
        f"<span style='font-size:12px;color:{conf_color};'>"
        f"● {t('confidence')}: {conf_label}</span>",
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # ── Key metrics row ───────────────────────────────────────────────────
    current_price = (info or {}).get("regularMarketPrice")
    prev_close = (info or {}).get("regularMarketPreviousClose")
    price_delta = None
    price_positive = None
    if current_price and prev_close:
        change_pct = (current_price - prev_close) / prev_close * 100
        price_delta = f"{change_pct:+.2f}% today"
        price_positive = change_pct >= 0

    gordon = result.fundamental.gordon
    fair_value_str = f"{gordon.fair_value:,.2f}" if gordon and gordon.fair_value else "N/A"
    upside_str = f"{gordon.upside_pct:+.1f}%" if gordon and gordon.upside_pct is not None else None
    upside_pos = (gordon.upside_pct or 0) > 0 if gordon else None

    capm = result.fundamental.capm
    pe = result.fundamental.pe

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card(
            t("metric_price"),
            f"{current_price:,.2f} {(info or {}).get('currency','')}" if current_price else "N/A",
            delta=price_delta,
            delta_positive=price_positive,
        )
    with col2:
        metric_card(
            t("metric_fair_value"),
            fair_value_str,
            delta=upside_str,
            delta_positive=upside_pos,
            help_text="Gordon Growth Model: P = D/(r-g). Shiller (2000).",
        )
    with col3:
        beta_val = capm.beta if capm else None
        beta_str = f"{beta_val:.2f}" if beta_val is not None else "N/A"
        beta_note = None
        if beta_val is not None:
            beta_note = "More volatile than market" if beta_val > 1 else "Less volatile than market"
        metric_card(t("metric_beta"), beta_str, delta=beta_note)
    with col4:
        ret = capm.required_return if capm else None
        ret_str = f"{ret:.1%}" if ret is not None else "N/A"
        metric_card(
            t("metric_capm_return"),
            ret_str,
            help_text=t("metric_capm_help"),
        )

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # ── Quick price chart ─────────────────────────────────────────────────
    if df_ind is not None:
        from app.charts import build_price_chart
        section_header(t("chart_price_title"))
        fig = build_price_chart(df_ind, result.technical, title="")
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # ── Summary notes ─────────────────────────────────────────────────────
    section_header(t("section_what_means"))
    for note in result.summary_notes:
        if note.startswith("──"):
            st.markdown(
                f"<div style='font-size:11px;color:#3b82f6;font-weight:600;"
                f"text-transform:uppercase;letter-spacing:0.1em;"
                f"margin:12px 0 6px;'>{note.replace('──','').strip()}</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"<div style='font-size:12px;color:#9ca3af;margin-bottom:6px;"
                f"line-height:1.5;padding-left:8px;border-left:2px solid #1f2937;'>"
                f"{note}</div>",
                unsafe_allow_html=True,
            )

    # ── Confidence reasons / warnings ─────────────────────────────────────
    all_warnings = result.confidence_reasons + result.technical.data_quality_warnings
    data_warnings(list(set(all_warnings)))
