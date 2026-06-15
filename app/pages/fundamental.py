"""Fundamental analysis page — Shiller models with educational context."""

from __future__ import annotations

import streamlit as st

from app.components import explain_box, metric_card, section_header, signal_badge
from app.i18n import t


def render(result, info: dict | None) -> None:
    if result is None:
        st.info(t("no_ticker_prompt"))
        return

    fund = result.fundamental
    section_header(
        t("nav_fundamental"),
        f"{result.ticker} — {t('fundamental_score')}: {fund.score:.0f}/100",
    )

    signal_badge(fund.signal, fund.score)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # ── CAPM metrics ──────────────────────────────────────────────────────
    capm = fund.capm
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card(
            t("metric_capm_return"),
            f"{capm.required_return:.1%}",
            help_text="r = rf + β(rm − rf)",
        )
    with col2:
        metric_card("Beta (β)", f"{capm.beta:.2f}")
    with col3:
        metric_card("Risk-free rate", f"{capm.risk_free_rate:.2%}")
    with col4:
        metric_card("Market risk premium", f"{capm.market_risk_premium:.2%}")

    col_l, col_r = st.columns([1, 1])

    with col_l:
        section_header("CAPM")
        explain_box(
            "Capital Asset Pricing Model",
            f"r<sub>i</sub> = r<sub>f</sub> + β · (r<sub>m</sub> − r<sub>f</sub>)<br><br>"
            f"Required return: <strong>{capm.required_return:.1%}</strong> "
            f"(β={capm.beta:.2f}, rf={capm.risk_free_rate:.2%}, "
            f"rm={capm.market_return:.1%}). "
            "This is the minimum return the market demands for this asset's "
            "level of systematic risk.",
            "Bodie, Kane, Marcus (2014) Investments, Ch.9",
        )

        # ── Gordon Growth Model ────────────────────────────────────────────
        section_header("Gordon Growth Model")
        gordon = fund.gordon
        if gordon and gordon.fair_value is not None:
            g_col1, g_col2 = st.columns(2)
            with g_col1:
                metric_card(
                    t("metric_fair_value"),
                    f"{gordon.fair_value:,.2f}",
                    delta=f"{gordon.upside_pct:+.1f}% upside" if gordon.upside_pct else None,
                    delta_positive=(gordon.upside_pct or 0) > 0,
                )
            with g_col2:
                metric_card("Dividend used", f"{gordon.dividend:.4f}")

            explain_box(
                "P = D / (r − g)",
                f"D (dividend) = {gordon.dividend:.4f}, "
                f"r (required return) = {gordon.discount_rate:.2%}, "
                f"g (growth rate) = {gordon.growth_rate:.2%}. "
                f"Fair value = <strong>{gordon.fair_value:,.2f}</strong>. "
                f"{'The stock appears <strong>undervalued</strong> vs intrinsic value.' if (gordon.upside_pct or 0) > 0 else 'The stock appears <strong>overvalued</strong> vs intrinsic value.'}",
                "Gordon (1962); Shiller (2000) Irrational Exuberance",
            )
            if gordon.assumption_warning:
                st.warning(gordon.assumption_warning)
        else:
            st.info(
                "Gordon Growth Model not applicable — "
                "this stock does not pay a dividend. "
                "Consider P/E and CAPM for valuation."
            )

    with col_r:
        # ── P/E Analysis ──────────────────────────────────────────────────
        section_header("P/E Ratio Analysis")
        pe = fund.pe
        p_col1, p_col2 = st.columns(2)
        with p_col1:
            metric_card(
                "Actual P/E (trailing)",
                f"{pe.actual_pe:.1f}" if pe.actual_pe else "N/A",
            )
        with p_col2:
            metric_card(
                "Theoretical P/E",
                f"{pe.theoretical_pe:.1f}" if pe.theoretical_pe else "N/A",
                help_text="1/(r−g) from the Shiller/Gordon framework",
            )

        interp_colors = {
            "undervalued": "#10b981",
            "fairly_valued": "#f59e0b",
            "overvalued": "#ef4444",
            "insufficient_data": "#6b7280",
        }
        interp_color = interp_colors.get(pe.interpretation, "#6b7280")
        st.markdown(
            f"<div style='margin:8px 0;font-size:13px;'>"
            f"Interpretation: <strong style='color:{interp_color};'>"
            f"{pe.interpretation.replace('_',' ').title()}</strong>"
            + (f" (gap: {pe.pe_gap:+.1f})" if pe.pe_gap else "")
            + "</div>",
            unsafe_allow_html=True,
        )

        explain_box(
            "P/E = 1 / (r − g)",
            "Shiller's framework: the theoretical P/E ratio is "
            "1/(r−g), where r is the required return and g is the "
            "long-term growth rate. A market P/E above this level "
            "implies investors expect higher growth than assumed, "
            "or the stock is overvalued.",
            "Shiller (2000) Irrational Exuberance, Ch.3",
        )

        # ── Score breakdown ────────────────────────────────────────────────
        section_header("Score breakdown")
        for comp_name, comp_score in fund.components.items():
            bar_color = "#10b981" if comp_score >= 60 else "#ef4444" if comp_score < 40 else "#f59e0b"
            st.markdown(
                f"""
                <div style='margin-bottom:10px;'>
                    <div style='display:flex;justify-content:space-between;
                                font-size:12px;color:#9ca3af;margin-bottom:4px;'>
                        <span>{comp_name.replace('_',' ').title()}</span>
                        <span style='color:{bar_color};font-weight:600;
                                     font-family:monospace;'>{comp_score:.0f}</span>
                    </div>
                    <div style='height:4px;background:#1f2937;border-radius:2px;'>
                        <div style='height:100%;width:{min(comp_score,100):.0f}%;
                                    background:{bar_color};border-radius:2px;'></div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # ── All fundamental notes ──────────────────────────────────────────────
    with st.expander("📝 Full analysis notes", expanded=False):
        for note in fund.notes:
            st.markdown(f"- {note}")
