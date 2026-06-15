"""Portfolio page — Swensen allocation builder, drift analysis, rebalancing."""

from __future__ import annotations

import streamlit as st

from app.components import explain_box, section_header
from app.i18n import t
from analysis.swensen import (
    CANONICAL_ALLOCATION,
    ASSET_CLASS_LABELS,
    AssetClass,
    analyse_portfolio,
    compute_target_amounts,
)


def render() -> None:
    section_header(t("portfolio_title"), t("portfolio_subtitle"))

    # ── Portfolio value input ─────────────────────────────────────────────
    col_val, col_info = st.columns([1, 2])
    with col_val:
        total_value = st.number_input(
            t("portfolio_total_value"),
            min_value=100.0,
            max_value=10_000_000.0,
            value=10_000.0,
            step=1000.0,
            format="%.0f",
        )

    with col_info:
        explain_box(
            "Swensen's model portfolio",
            "David Swensen (Yale CIO, 1985–2021) demonstrated that "
            "individual investors can achieve superior long-term returns "
            "with a simple, low-cost allocation across 6 asset classes "
            "with low correlation to each other. "
            "Annual rebalancing at the 5pp threshold is the key discipline.",
            "Swensen (2005) Unconventional Success, Ch.8",
        )

    # ── Current allocation sliders ─────────────────────────────────────────
    section_header("Current allocation", "Adjust sliders to match your portfolio")

    lang = st.session_state.get("lang", "en")
    current_alloc: dict[AssetClass, float] = {}
    cols = st.columns(3)

    for idx, cls in enumerate(AssetClass):
        label = ASSET_CLASS_LABELS[cls][lang]
        default_pct = int(CANONICAL_ALLOCATION[cls] * 100)
        with cols[idx % 3]:
            pct = st.slider(
                label,
                min_value=0, max_value=100,
                value=default_pct,
                step=1,
                key=f"alloc_{cls.value}",
            )
            current_alloc[cls] = pct / 100

    # ── Run analysis ──────────────────────────────────────────────────────
    try:
        portfolio_result = analyse_portfolio(
            current_allocation=current_alloc,
            total_value=total_value,
            horizon_years=10,
        )
    except Exception as exc:
        st.error(f"Analysis error: {exc}")
        return

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # ── Summary metrics ───────────────────────────────────────────────────
    m1, m2, m3, m4 = st.columns(4)
    score_color = (
        "#10b981" if portfolio_result.swensen_score >= 75
        else "#f59e0b" if portfolio_result.swensen_score >= 50
        else "#ef4444"
    )
    with m1:
        st.metric(t("portfolio_swensen_score"), f"{portfolio_result.swensen_score:.0f}/100")
    with m2:
        rebal_label = t("portfolio_rebalance_needed") if portfolio_result.needs_rebalancing else t("portfolio_balanced")
        st.metric("Status", rebal_label)
    with m3:
        st.metric(t("portfolio_annual_cost"), f"{portfolio_result.annual_cost_estimate:,.2f}")
    with m4:
        st.metric(
            "Actions needed",
            str(len(portfolio_result.rebalancing_actions)),
        )

    # ── Allocation charts ─────────────────────────────────────────────────
    from app.charts import build_allocation_chart, build_drift_chart

    current_named = {
        ASSET_CLASS_LABELS[p.asset_class][lang]: p.current_weight
        for p in portfolio_result.positions
    }
    target_named = {
        ASSET_CLASS_LABELS[p.asset_class][lang]: p.target_weight
        for p in portfolio_result.positions
    }

    col_donut, col_drift = st.columns([1, 1])
    with col_donut:
        fig_alloc = build_allocation_chart(current_named, target_named, "Allocation")
        st.plotly_chart(fig_alloc, use_container_width=True, config={"displayModeBar": False})
    with col_drift:
        fig_drift = build_drift_chart(portfolio_result.positions, "Drift from target (pp)")
        st.plotly_chart(fig_drift, use_container_width=True, config={"displayModeBar": False})

    # ── Rebalancing actions table ─────────────────────────────────────────
    if portfolio_result.rebalancing_actions:
        section_header("Rebalancing actions required")
        for action in portfolio_result.rebalancing_actions:
            label = ASSET_CLASS_LABELS[action.asset_class][lang]
            color = "#ef4444" if action.action == "sell" else "#10b981"
            action_label = "SELL" if action.action == "sell" else "BUY"
            st.markdown(
                f"""
                <div style='background:#111827;border:1px solid #1f2937;
                            border-left:3px solid {color};border-radius:8px;
                            padding:12px 16px;margin-bottom:8px;'>
                    <div style='display:flex;justify-content:space-between;
                                align-items:center;'>
                        <div>
                            <span style='font-size:14px;font-weight:600;
                                         color:#f9fafb;'>{label}</span>
                            <span style='font-size:11px;color:#6b7280;
                                         margin-left:8px;'>{action.etf_ticker}</span>
                        </div>
                        <div style='text-align:right;'>
                            <span style='background:{color}18;color:{color};
                                         font-size:11px;font-weight:700;padding:3px 10px;
                                         border-radius:99px;letter-spacing:0.05em;'>
                                {action_label}
                            </span>
                            <div style='font-family:monospace;font-size:13px;
                                         color:#f9fafb;margin-top:4px;'>
                                {action.amount:,.0f}
                            </div>
                        </div>
                    </div>
                    <div style='font-size:11px;color:#6b7280;margin-top:6px;'>
                        {action.rationale}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.success("Portfolio is within the 5pp threshold. No rebalancing needed.")

    # ── Target amounts table ──────────────────────────────────────────────
    section_header("Target amounts", "How much to allocate to each ETF")
    amounts = compute_target_amounts(total_value)
    from analysis.swensen import ETF_RECOMMENDATIONS
    for cls, amount in amounts.items():
        etf = ETF_RECOMMENDATIONS[cls]
        label = ASSET_CLASS_LABELS[cls][lang]
        st.markdown(
            f"""
            <div style='display:flex;justify-content:space-between;
                        align-items:center;padding:8px 0;
                        border-bottom:1px solid #1f2937;font-size:13px;'>
                <div>
                    <span style='color:#e5e7eb;'>{label}</span>
                    <span style='color:#3b82f6;font-family:monospace;
                                 font-size:11px;margin-left:8px;'>{etf.ticker}</span>
                    <span style='color:#4b5563;font-size:10px;
                                 margin-left:6px;'>TER {etf.expense_ratio:.2%}</span>
                </div>
                <span style='font-family:monospace;font-weight:600;color:#f9fafb;'>
                    {amount:,.0f}
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ── Notes ──────────────────────────────────────────────────────────────
    with st.expander("📝 Analysis notes", expanded=False):
        for note in portfolio_result.notes:
            st.markdown(f"- {note}")
