"""
Mapping layer: domain dataclasses → Pydantic response schemas.

Each function in this module converts one analysis dataclass into its
corresponding Pydantic response model. This decouples the domain layer
from the API contract — if the domain model changes, only the mapper
needs to update; the schema and the router are insulated.

All functions are pure: no I/O, no side effects.

Design note: we intentionally do NOT use Pydantic's from_orm() here
because our domain objects are frozen dataclasses, not ORM models.
Explicit field mapping is more readable and catches breaking changes
at import time rather than at runtime.
"""

from __future__ import annotations

from analysis.fundamentals import FundamentalScore
from analysis.scoring import CompositeResult
from analysis.swensen import SwensenPortfolioResult
from analysis.technical import TechnicalScore
from backend.schemas import (
    ADXOut, AnalyzeResponse, BollingerOut, BreakEvenOut,
    CAPMOut, DCAOut, FundamentalOut, GordonOut,
    GrowthProjectionOut, MACDOut, MovingAverageOut,
    OBVOut, PERatioOut, PortfolioResponse, PositionOut,
    RebalancingActionOut, RiskMetricsOut, RSIOut, ScenarioOut,
    SimulateResponse, SimulateYearOut, TechnicalOut,
    YearProjectionOut,
)
from simulation.simulator import SimulationResult


# ---------------------------------------------------------------------------
# Analyse
# ---------------------------------------------------------------------------

def to_analyze_response(result: CompositeResult) -> AnalyzeResponse:
    """Convert a CompositeResult to the /v1/analyze response schema."""
    return AnalyzeResponse(
        ticker=result.ticker,
        composite_score=result.composite_score,
        signal=result.signal,
        strategy_name=result.strategy_name,
        weights=result.weights,
        score_breakdown=result.score_breakdown,
        confidence=result.confidence,
        confidence_reasons=result.confidence_reasons,
        fundamental=_to_fundamental_out(result.fundamental),
        technical=_to_technical_out(result.technical),
        summary_notes=result.summary_notes,
        analysed_at=result.analysed_at,
        disclaimer=result.disclaimer,
    )


def _to_fundamental_out(f: FundamentalScore) -> FundamentalOut:
    capm = f.capm
    gordon = f.gordon
    pe = f.pe

    return FundamentalOut(
        score=f.score,
        signal=f.signal,
        components=f.components,
        capm=CAPMOut(
            required_return=capm.required_return,
            risk_free_rate=capm.risk_free_rate,
            market_return=capm.market_return,
            beta=capm.beta,
            market_risk_premium=capm.market_risk_premium,
        ),
        gordon=GordonOut(
            fair_value=gordon.fair_value,
            current_price=gordon.current_price,
            dividend=gordon.dividend,
            discount_rate=gordon.discount_rate,
            growth_rate=gordon.growth_rate,
            upside_pct=gordon.upside_pct,
            assumption_warning=gordon.assumption_warning,
        ) if gordon is not None else None,
        pe=PERatioOut(
            actual_pe=pe.actual_pe,
            theoretical_pe=pe.theoretical_pe,
            forward_pe=pe.forward_pe,
            pe_gap=pe.pe_gap,
            interpretation=pe.interpretation,
        ),
        notes=f.notes,
    )


def _to_technical_out(t: TechnicalScore) -> TechnicalOut:
    rsi = t.rsi
    macd = t.macd
    bb = t.bollinger
    ma = t.moving_averages
    obv = t.obv
    adx = t.adx

    return TechnicalOut(
        score=t.score,
        signal=t.signal,
        components=t.components,
        rsi=RSIOut(
            value=rsi.value,
            signal=rsi.signal.value,
            overbought_threshold=rsi.overbought_threshold,
            oversold_threshold=rsi.oversold_threshold,
        ),
        macd=MACDOut(
            macd=macd.macd,
            signal_line=macd.signal_line,
            histogram=macd.histogram,
            signal=macd.signal.value,
            is_bullish_crossover=macd.is_bullish_crossover,
            is_bearish_crossover=macd.is_bearish_crossover,
        ),
        bollinger=BollingerOut(
            upper=bb.upper,
            middle=bb.middle,
            lower=bb.lower,
            bandwidth=bb.bandwidth,
            percent_b=bb.percent_b,
            signal=bb.signal.value,
        ),
        moving_averages=MovingAverageOut(
            sma_20=ma.sma_20,
            sma_50=ma.sma_50,
            sma_200=ma.sma_200,
            ema_20=ma.ema_20,
            current_price=ma.current_price,
            golden_cross=ma.golden_cross,
            death_cross=ma.death_cross,
            price_above_sma200=ma.price_above_sma200,
            signal=ma.signal.value,
        ),
        obv=OBVOut(
            current_obv=obv.current_obv,
            obv_sma=obv.obv_sma,
            volume_trend=obv.volume_trend,
            confirms_price_trend=obv.confirms_price_trend,
            signal=obv.signal.value,
        ),
        adx=ADXOut(
            adx=adx.adx,
            plus_di=adx.plus_di,
            minus_di=adx.minus_di,
            trend_strength=adx.trend_strength,
            signal=adx.signal.value,
        ),
        notes=t.notes,
        data_quality_warnings=t.data_quality_warnings,
    )


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------

def to_portfolio_response(result: SwensenPortfolioResult) -> PortfolioResponse:
    """Convert a SwensenPortfolioResult to the /v1/portfolio response schema."""
    proj = result.projection

    return PortfolioResponse(
        positions=[
            PositionOut(
                asset_class=p.asset_class.value,
                current_weight=p.current_weight,
                target_weight=p.target_weight,
                current_value=p.current_value,
                drift=p.drift,
                drift_pct=p.drift_pct,
                needs_rebalancing=p.needs_rebalancing,
                action=p.action,
                etf_ticker=p.etf.ticker,
                etf_name=p.etf.name,
                etf_expense_ratio=p.etf.expense_ratio,
                etf_ucits_alternative=p.etf.ucits_alternative,
            )
            for p in result.positions
        ],
        rebalancing_actions=[
            RebalancingActionOut(
                asset_class=a.asset_class.value,
                action=a.action,
                amount=a.amount,
                current_weight=a.current_weight,
                target_weight=a.target_weight,
                etf_ticker=a.etf_ticker,
                rationale=a.rationale,
            )
            for a in result.rebalancing_actions
        ],
        total_portfolio_value=result.total_portfolio_value,
        swensen_score=result.swensen_score,
        needs_rebalancing=result.needs_rebalancing,
        projection=GrowthProjectionOut(
            initial_investment=proj.initial_investment,
            horizon_years=proj.horizon_years,
            pessimistic_rate=proj.pessimistic_rate,
            base_rate=proj.base_rate,
            optimistic_rate=proj.optimistic_rate,
            pessimistic_value=proj.pessimistic_value,
            base_value=proj.base_value,
            optimistic_value=proj.optimistic_value,
            year_by_year=[
                YearProjectionOut(
                    year=int(y["year"]),
                    pessimistic=y["pessimistic"],
                    base=y["base"],
                    optimistic=y["optimistic"],
                )
                for y in proj.year_by_year
            ],
        ),
        annual_cost_estimate=result.annual_cost_estimate,
        notes=result.notes,
        disclaimer=result.disclaimer,
    )


# ---------------------------------------------------------------------------
# Simulate
# ---------------------------------------------------------------------------

def to_simulate_response(result: SimulationResult) -> SimulateResponse:
    """Convert a SimulationResult to the /v1/simulate response schema."""
    risk = result.risk
    be = result.break_even

    return SimulateResponse(
        ticker=result.ticker,
        initial_investment=result.initial_investment,
        horizon_years=result.horizon_years,
        scenarios=[
            ScenarioOut(
                label=s.label,
                annual_rate=s.annual_rate,
                final_value=s.final_value,
                total_gain=s.total_gain,
                gain_pct=s.gain_pct,
                cagr=s.cagr,
            )
            for s in result.scenarios
        ],
        dca=DCAOut(
            monthly_contribution=result.dca.monthly_contribution,
            total_contributed=result.dca.total_contributed,
            final_value_base=result.dca.final_value_base,
            gain_from_dca=result.dca.gain_from_dca,
            effective_cagr=result.dca.effective_cagr,
        ) if result.dca else None,
        risk=RiskMetricsOut(
            annual_volatility=risk.annual_volatility,
            value_at_risk_95=risk.value_at_risk_95,
            max_drawdown_estimate=risk.max_drawdown_estimate,
            sharpe_ratio=risk.sharpe_ratio,
            break_even_years=risk.break_even_years,
            volatility_source=risk.volatility_source,
        ),
        break_even=BreakEvenOut(
            break_even_year_base=be.break_even_year_base,
            break_even_year_pessimistic=be.break_even_year_pessimistic,
            gordon_fair_value=be.gordon_fair_value,
            current_price=be.current_price,
            is_undervalued=be.is_undervalued,
            margin_of_safety=be.margin_of_safety,
        ),
        year_by_year=[
            SimulateYearOut(
                year=y.year,
                pessimistic=y.pessimistic,
                base=y.base,
                optimistic=y.optimistic,
                dca_base=y.dca_base,
            )
            for y in result.year_by_year
        ],
        assumptions={k: str(v) for k, v in result.assumptions.items()},
        notes=result.notes,
        disclaimer=result.disclaimer,
    )
