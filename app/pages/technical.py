"""Technical analysis page — charts, signal table, Murphy explanations."""

from __future__ import annotations

import streamlit as st

from app.components import (
    data_warnings,
    explain_box,
    section_header,
    signal_row,
)
from app.i18n import t


def render(result, df_ind) -> None:
    if result is None:
        st.info(t("no_ticker_prompt"))
        return

    tech = result.technical
    section_header(
        t("nav_technical"),
        f"{result.ticker} — {t('technical_score')}: {tech.score:.0f}/100",
    )

    # ── Price + indicators chart ──────────────────────────────────────────
    if df_ind is not None:
        from app.charts import build_price_chart
        fig = build_price_chart(df_ind, tech, title=t("chart_price_title"))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── Signal table + explanations side by side ──────────────────────────
    col_signals, col_explain = st.columns([1, 1])

    with col_signals:
        section_header(t("section_tech_signals"))

        rsi = tech.rsi
        rsi_val = f"{rsi.value:.1f}" if rsi.value is not None else "N/A"
        rsi_zone = (
            "Oversold" if rsi.signal.value == "buy"
            else "Overbought" if rsi.signal.value == "sell"
            else "Neutral zone"
        )
        signal_row(
            t("rsi_label"),
            rsi.signal.value,
            f"{rsi_val} — {rsi_zone}",
        )

        macd = tech.macd
        macd_str = "N/A"
        if macd.histogram is not None:
            cross = "Bullish crossover" if macd.is_bullish_crossover else (
                "Bearish crossover" if macd.is_bearish_crossover else
                ("Above zero" if macd.histogram > 0 else "Below zero")
            )
            macd_str = cross
        signal_row(t("macd_label"), macd.signal.value, macd_str)

        bb = tech.bollinger
        bb_str = "N/A"
        if bb.percent_b is not None:
            zone = (
                "Near lower band" if bb.signal.value == "buy"
                else "Near upper band" if bb.signal.value == "sell"
                else "Inside bands"
            )
            bb_str = f"%B={bb.percent_b:.2f} — {zone}"
        signal_row(t("bb_label"), bb.signal.value, bb_str)

        ma = tech.moving_averages
        ma_str = "Golden Cross" if ma.golden_cross else (
            "Death Cross" if ma.death_cross else "No crossover"
        )
        if ma.sma_50 and ma.sma_200:
            ma_str += f" (SMA50={ma.sma_50:.2f} / SMA200={ma.sma_200:.2f})"
        signal_row(t("sma_label"), ma.signal.value, ma_str)

        obv = tech.obv
        obv_str = f"Volume {obv.volume_trend}"
        if obv.confirms_price_trend:
            obv_str += " — confirms trend"
        else:
            obv_str += " — diverges from price"
        signal_row(t("obv_label"), obv.signal.value, obv_str)

        adx = tech.adx
        adx_str = f"ADX={adx.adx:.1f} — {adx.trend_strength}" if adx.adx else "N/A"
        if adx.plus_di and adx.minus_di:
            adx_str += f" (+DI={adx.plus_di:.1f} / -DI={adx.minus_di:.1f})"
        signal_row(t("adx_label"), adx.signal.value, adx_str)

    with col_explain:
        section_header(t("section_what_means"))

        explain_box(
            "RSI — Relative Strength Index",
            f"Measures momentum on a 0–100 scale. "
            f"Below {rsi.oversold_threshold:.0f} = <strong>oversold</strong> "
            f"(potential buying opportunity). "
            f"Above {rsi.overbought_threshold:.0f} = <strong>overbought</strong> "
            f"(potential reversal down). "
            f"Neutral zone {rsi.oversold_threshold:.0f}–{rsi.overbought_threshold:.0f} "
            f"means no extreme signal.",
            "Murphy (1999) Technical Analysis, p.225",
        )

        explain_box(
            "MACD — Moving Average Convergence/Divergence",
            "Tracks the relationship between two EMAs (12 and 26 days). "
            "A <strong>bullish crossover</strong> (MACD crosses above signal line) "
            "signals rising momentum. "
            "A <strong>bearish crossover</strong> signals falling momentum. "
            "The histogram shows the strength of the crossover.",
            "Murphy (1999) Technical Analysis, p.233",
        )

        explain_box(
            "Golden Cross / Death Cross",
            "The <strong>Golden Cross</strong> (SMA50 crosses above SMA200) is "
            "one of the most widely watched long-term bullish signals on Wall Street. "
            "The <strong>Death Cross</strong> (SMA50 below SMA200) signals a "
            "long-term bearish trend. Price above SMA200 = in a bull market.",
            "Murphy (1999) Technical Analysis, p.196",
        )

    data_warnings(tech.data_quality_warnings)
