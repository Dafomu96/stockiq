"""Simulator page — P&L projection with scenarios, DCA, and risk metrics."""

from __future__ import annotations

import streamlit as st

from app.components import explain_box, metric_card, section_header
from app.i18n import t
from simulation.simulator import simulate


def render(result) -> None:
    section_header(t("sim_title"), t("sim_subtitle"))

    # ── Inputs ────────────────────────────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    with col1:
        ticker = st.text_input("Ticker", value=result.ticker if result else "AAPL")
        investment = st.number_input(t("sim_investment"), min_value=100.0, value=10_000.0, step=500.0)
    with col2:
        horizon = st.slider(t("sim_horizon"), min_value=1, max_value=30, value=10)
        monthly = st.number_input(t("sim_monthly"), min_value=0.0, value=0.0, step=50.0)
    with col3:
        volatility = st.number_input(
            "Annual volatility (%)", min_value=1.0, max_value=100.0,
            value=18.0, step=1.0,
            help="Historical annualised volatility. Use 15–20% for large-cap equities."
        ) / 100

    run_btn = st.button(t("sim_run_btn"), type="primary")

    if not run_btn and result is None:
        st.info(t("no_ticker_prompt"))
        return

    # ── Extract CAPM and Gordon values from CompositeResult if available ──
    capm_return = None
    gordon_fv = None
    current_price = None

    if result is not None:
        capm_return = result.fundamental.capm.required_return
        gordon = result.fundamental.gordon
        if gordon and gordon.fair_value:
            gordon_fv = gordon.fair_value
            current_price = gordon.current_price

    # ── Run simulation ────────────────────────────────────────────────────
    try:
        sim = simulate(
            ticker=ticker,
            initial_investment=investment,
            horizon_years=horizon,
            monthly_contribution=monthly,
            annual_volatility=volatility,
            capm_required_return=capm_return,
            gordon_fair_value=gordon_fv,
            current_price=current_price,
        )
    except Exception as exc:
        st.error(f"Simulation error: {exc}")
        return

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # ── Scenario summary metrics ──────────────────────────────────────────
    pess, base, opt = sim.scenarios
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        metric_card(
            f"📉 {t('sim_pessimistic')} ({pess.annual_rate:.0%}/yr)",
            f"{pess.final_value:,.0f}",
            delta=f"+{pess.gain_pct:.1f}%",
            delta_positive=True,
        )
    with c2:
        metric_card(
            f"📊 {t('sim_base')} ({base.annual_rate:.1%}/yr)",
            f"{base.final_value:,.0f}",
            delta=f"+{base.gain_pct:.1f}%",
            delta_positive=True,
        )
    with c3:
        metric_card(
            f"📈 {t('sim_optimistic')} ({opt.annual_rate:.0%}/yr)",
            f"{opt.final_value:,.0f}",
            delta=f"+{opt.gain_pct:.1f}%",
            delta_positive=True,
        )
    with c4:
        if sim.dca:
            metric_card(
                f"🔄 DCA base (+{monthly:,.0f}/mo)",
                f"{sim.dca.final_value_base:,.0f}",
                delta=f"+{sim.dca.gain_from_dca:,.0f} vs lump sum",
                delta_positive=True,
            )
        else:
            metric_card(
                "💰 Total invested",
                f"{investment:,.0f}",
                delta="Lump sum only",
            )

    # ── Projection chart ──────────────────────────────────────────────────
    from app.charts import build_simulation_chart
    fig = build_simulation_chart(sim, show_dca=monthly > 0, title=t("sim_title"))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # ── Risk metrics + break-even ─────────────────────────────────────────
    col_risk, col_be = st.columns([1, 1])

    with col_risk:
        section_header("Risk metrics")
        risk = sim.risk
        r1, r2 = st.columns(2)
        with r1:
            metric_card(t("sim_sharpe"), f"{risk.sharpe_ratio:.2f}",
                        help_text="(base_rate − rf) / volatility. >1 = good risk/return.")
            metric_card(t("sim_max_dd"), f"{risk.max_drawdown_estimate:.1%}",
                        help_text="Estimated peak-to-trough decline (heuristic).")
        with r2:
            metric_card(t("sim_var"), f"{risk.value_at_risk_95:.1%}",
                        help_text="Parametric VaR 95% — max expected 1-year loss.")
            metric_card("Break-even after loss",
                        f"{risk.break_even_years:.1f} yrs" if risk.break_even_years > 0 else "< 1 yr",
                        help_text="Years to recover from a VaR-95 loss at the base rate.")

        explain_box(
            "VaR and Sharpe ratio",
            f"VaR(95%) = base_rate − 1.645 × σ = "
            f"{base.annual_rate:.1%} − 1.645 × {risk.annual_volatility:.1%} = "
            f"{risk.value_at_risk_95:.1%} expected max loss. "
            f"Sharpe ratio = (r − rf) / σ = {risk.sharpe_ratio:.2f}. "
            f"A ratio above 1.0 is generally considered attractive.",
            "Bodie, Kane, Marcus (2014) Investments, Ch.5; Sharpe (1994)",
        )

    with col_be:
        section_header("Margin of safety")
        be = sim.break_even
        if be.margin_of_safety is not None and be.current_price is not None:
            mos = be.margin_of_safety
            color = "#10b981" if mos > 0 else "#ef4444"
            st.markdown(
                f"""
                <div style='background:#111827;border:1px solid #1f2937;
                            border-left:3px solid {color};border-radius:8px;
                            padding:14px;'>
                    <div style='font-size:13px;color:#9ca3af;'>Gordon fair value</div>
                    <div style='font-family:monospace;font-size:22px;
                                font-weight:600;color:#f9fafb;margin:4px 0;'>
                        {be.gordon_fair_value:,.2f}
                    </div>
                    <div style='font-size:12px;color:{color};'>
                        {'▲ Undervalued' if mos > 0 else '▼ Overvalued'}:
                        {abs(mos):.1%} {'discount' if mos > 0 else 'premium'}
                        to intrinsic value
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            explain_box(
                "Margin of safety",
                "Benjamin Graham's principle: buy at a discount to intrinsic value "
                "to protect against errors in the valuation model. "
                f"Current price: {be.current_price:,.2f}. "
                f"Gordon fair value: {be.gordon_fair_value:,.2f}. "
                f"Margin: {'positive' if mos > 0 else 'negative'} {abs(mos):.1%}.",
                "Graham (1949) The Intelligent Investor; Shiller (2000)",
            )
        else:
            st.info("No Gordon fair value available (no dividend). "
                    "Margin of safety analysis requires dividend data.")

    # ── Assumptions transparency ──────────────────────────────────────────
    with st.expander(f"🔍 {t('section_assumptions')}", expanded=False):
        for key, val in sim.assumptions.items():
            st.markdown(f"**{key.replace('_',' ').title()}:** {val}")

    # ── Educational notes ──────────────────────────────────────────────────
    with st.expander("📝 Analysis notes", expanded=False):
        for note in sim.notes:
            st.markdown(f"- {note}")

    st.markdown(
        f"<div style='font-size:11px;color:#4b5563;margin-top:12px;'>"
        f"{sim.disclaimer}</div>",
        unsafe_allow_html=True,
    )
