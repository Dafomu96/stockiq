"""
Plotly chart builders for StockIQ.

All chart functions are pure: they receive data, return a Plotly Figure,
and have no side effects. Pages call st.plotly_chart(build_xxx(...)).

Design language:
    - Dark background matching the app theme (#0a0e1a / #111827)
    - Blue (#3b82f6) as primary accent
    - Green (#10b981) for buy signals / positive moves
    - Red (#ef4444) for sell signals / negative moves
    - Amber (#f59e0b) for neutral / warnings
    - JetBrains Mono for axis labels
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from analysis.technical import TechnicalScore
from simulation.simulator import SimulationResult

# ── Shared theme ────────────────────────────────────────────────────────────

_BG = "#0a0e1a"
_PAPER = "#111827"
_GRID = "#1f2937"
_TEXT = "#9ca3af"
_WHITE = "#f9fafb"
_BLUE = "#3b82f6"
_GREEN = "#10b981"
_RED = "#ef4444"
_AMBER = "#f59e0b"
_PURPLE = "#8b5cf6"

_BASE_LAYOUT = dict(
    paper_bgcolor=_PAPER,
    plot_bgcolor=_BG,
    font=dict(family="JetBrains Mono, monospace", size=11, color=_TEXT),
    margin=dict(l=8, r=8, t=36, b=8),
    legend=dict(
        bgcolor="rgba(0,0,0,0)",
        bordercolor=_GRID,
        borderwidth=0,
        font=dict(size=10),
    ),
    xaxis=dict(
        gridcolor=_GRID, zerolinecolor=_GRID,
        showline=False, tickfont=dict(size=10),
    ),
    yaxis=dict(
        gridcolor=_GRID, zerolinecolor=_GRID,
        showline=False, tickfont=dict(size=10),
    ),
)


def _apply_base(fig: go.Figure, title: str = "") -> go.Figure:
    layout = dict(**_BASE_LAYOUT)
    if title:
        layout["title"] = dict(
            text=title, font=dict(size=13, color=_WHITE), x=0, xanchor="left"
        )
    fig.update_layout(**layout)
    return fig


# ── Price + indicators chart ────────────────────────────────────────────────

def build_price_chart(
    df: pd.DataFrame,
    technical: TechnicalScore,
    title: str = "Price + indicators",
) -> go.Figure:
    """Candlestick chart with SMA20/50/200 and Bollinger Bands overlaid.

    Subplots:
        Row 1 (70%): Candlestick + moving averages + Bollinger Bands
        Row 2 (15%): RSI panel with overbought/oversold zones
        Row 3 (15%): MACD histogram + signal lines

    Args:
        df: OHLCV DataFrame from MarketDataFetcher (UTC DatetimeIndex).
        technical: TechnicalScore with indicator values.
        title: Chart title.

    Returns:
        Plotly Figure ready for st.plotly_chart().
    """
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        row_heights=[0.65, 0.175, 0.175],
        vertical_spacing=0.02,
        subplot_titles=("", "RSI (14)", "MACD"),
    )

    # ── Row 1: Candlestick ────────────────────────────────────────────────
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"],
        increasing_line_color=_GREEN,
        decreasing_line_color=_RED,
        increasing_fillcolor=_GREEN,
        decreasing_fillcolor=_RED,
        name="Price",
        showlegend=False,
        line=dict(width=1),
    ), row=1, col=1)

    # Moving averages
    ma = technical.moving_averages
    _ma_pairs = [
        ("SMA_20", ma.sma_20, _BLUE, "SMA 20"),
        ("SMA_50", ma.sma_50, _AMBER, "SMA 50"),
        ("SMA_200", ma.sma_200, _PURPLE, "SMA 200"),
        ("EMA_20", ma.ema_20, "#06b6d4", "EMA 20"),
    ]
    for col_name, val, color, label in _ma_pairs:
        ma_col = f"SMA_{col_name.split('_')[1]}" if "SMA" in col_name else f"EMA_{col_name.split('_')[1]}"
        if val is not None and ma_col in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index, y=df[ma_col],
                mode="lines", line=dict(color=color, width=1.2),
                name=label, opacity=0.85,
            ), row=1, col=1)

    # Bollinger Bands
    bb_upper_col = [c for c in df.columns if c.startswith("BBU_")]
    bb_lower_col = [c for c in df.columns if c.startswith("BBL_")]
    if bb_upper_col and bb_lower_col:
        fig.add_trace(go.Scatter(
            x=df.index, y=df[bb_upper_col[0]],
            mode="lines", line=dict(color=_BLUE, width=0.8, dash="dot"),
            name="BB Upper", opacity=0.5, showlegend=False,
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df.index, y=df[bb_lower_col[0]],
            mode="lines", line=dict(color=_BLUE, width=0.8, dash="dot"),
            fill="tonexty", fillcolor="rgba(59,130,246,0.05)",
            name="Bollinger Bands", opacity=0.5,
        ), row=1, col=1)

    # ── Row 2: RSI ────────────────────────────────────────────────────────
    rsi_col = "RSI_14"
    if rsi_col in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df[rsi_col],
            mode="lines", line=dict(color=_BLUE, width=1.5),
            name="RSI", showlegend=False,
        ), row=2, col=1)
        # Overbought / oversold zones
        fig.add_hrect(
            y0=70, y1=100, row=2, col=1,
            fillcolor=f"{_RED}18", line_width=0,
        )
        fig.add_hrect(
            y0=0, y1=30, row=2, col=1,
            fillcolor=f"{_GREEN}18", line_width=0,
        )
        fig.add_hline(
            y=70, row=2, col=1,
            line=dict(color=_RED, width=0.8, dash="dot"),
        )
        fig.add_hline(
            y=30, row=2, col=1,
            line=dict(color=_GREEN, width=0.8, dash="dot"),
        )
        fig.update_yaxes(range=[0, 100], row=2)

    # ── Row 3: MACD ───────────────────────────────────────────────────────
    macd_col = "MACD_12_26_9"
    sig_col = "MACDs_12_26_9"
    hist_col = "MACDh_12_26_9"

    if hist_col in df.columns:
        hist = df[hist_col]
        colors = [_GREEN if v >= 0 else _RED for v in hist]
        fig.add_trace(go.Bar(
            x=df.index, y=hist,
            marker_color=colors, opacity=0.7,
            name="MACD Histogram", showlegend=False,
        ), row=3, col=1)

    if macd_col in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df[macd_col],
            mode="lines", line=dict(color=_BLUE, width=1.2),
            name="MACD", showlegend=False,
        ), row=3, col=1)

    if sig_col in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df[sig_col],
            mode="lines", line=dict(color=_AMBER, width=1.2),
            name="Signal", showlegend=False,
        ), row=3, col=1)

    # ── Layout ────────────────────────────────────────────────────────────
    fig = _apply_base(fig, title)
    fig.update_layout(
        height=520,
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
    )
    fig.update_xaxes(showgrid=True, gridcolor=_GRID)
    fig.update_yaxes(showgrid=True, gridcolor=_GRID)

    return fig


# ── Swensen allocation donut ─────────────────────────────────────────────────

def build_allocation_chart(
    current: dict[str, float],
    target: dict[str, float],
    title: str = "Portfolio allocation",
) -> go.Figure:
    """Side-by-side donut charts: current vs target Swensen allocation.

    Args:
        current: Dict of asset_class_name → current weight (decimal).
        target: Dict of asset_class_name → target weight (decimal).
        title: Chart title.

    Returns:
        Plotly Figure with two donuts.
    """
    colors = [_BLUE, _GREEN, "#06b6d4", _AMBER, _PURPLE, "#f97316"]
    labels = list(current.keys())

    fig = make_subplots(
        rows=1, cols=2,
        specs=[[{"type": "pie"}, {"type": "pie"}]],
        subplot_titles=("Current", "Target (Swensen)"),
    )

    fig.add_trace(go.Pie(
        labels=labels,
        values=[current[k] * 100 for k in labels],
        hole=0.6,
        marker=dict(colors=colors, line=dict(color=_BG, width=2)),
        textinfo="label+percent",
        textfont=dict(size=10),
        showlegend=False,
    ), row=1, col=1)

    fig.add_trace(go.Pie(
        labels=labels,
        values=[target.get(k, 0) * 100 for k in labels],
        hole=0.6,
        marker=dict(colors=colors, line=dict(color=_BG, width=2)),
        textinfo="label+percent",
        textfont=dict(size=10),
        showlegend=False,
    ), row=1, col=2)

    fig = _apply_base(fig, title)
    fig.update_layout(height=300)
    return fig


# ── Simulator P&L projection chart ──────────────────────────────────────────

def build_simulation_chart(
    result: SimulationResult,
    show_dca: bool = True,
    title: str = "Portfolio projection",
) -> go.Figure:
    """Area chart with three scenario bands + optional DCA line.

    Args:
        result: SimulationResult from simulator.simulate().
        show_dca: Whether to overlay the DCA base line.
        title: Chart title.

    Returns:
        Plotly Figure ready for st.plotly_chart().
    """
    fig = go.Figure()
    years = [d.year for d in result.year_by_year]

    # Optimistic fill (upper band)
    opt_values = [d.optimistic for d in result.year_by_year]
    pess_values = [d.pessimistic for d in result.year_by_year]
    base_values = [d.base for d in result.year_by_year]

    # Optimistic–pessimistic band fill
    fig.add_trace(go.Scatter(
        x=years + years[::-1],
        y=opt_values + pess_values[::-1],
        fill="toself",
        fillcolor=f"{_BLUE}12",
        line=dict(color="rgba(0,0,0,0)"),
        hoverinfo="skip",
        showlegend=False,
        name="Range",
    ))

    # Pessimistic line
    fig.add_trace(go.Scatter(
        x=years, y=pess_values,
        mode="lines",
        line=dict(color=_RED, width=1.5, dash="dot"),
        name="Pessimistic (4%)",
    ))

    # Base line
    fig.add_trace(go.Scatter(
        x=years, y=base_values,
        mode="lines+markers",
        line=dict(color=_BLUE, width=2.5),
        marker=dict(size=5, color=_BLUE),
        name=f"Base ({result.scenarios[1].annual_rate:.1%})",
    ))

    # Optimistic line
    fig.add_trace(go.Scatter(
        x=years, y=opt_values,
        mode="lines",
        line=dict(color=_GREEN, width=1.5, dash="dot"),
        name="Optimistic (10%)",
    ))

    # DCA line
    if show_dca and result.dca is not None:
        dca_values = [d.dca_base for d in result.year_by_year]
        fig.add_trace(go.Scatter(
            x=years, y=dca_values,
            mode="lines",
            line=dict(color=_AMBER, width=2, dash="dash"),
            name=f"DCA +{result.dca.monthly_contribution:,.0f}/mo",
        ))

    # Initial investment reference line
    fig.add_hline(
        y=result.initial_investment,
        line=dict(color=_MUTED if True else _GRID, width=1, dash="dot"),
        annotation_text="Initial investment",
        annotation_font=dict(size=10, color="#6b7280"),
    )

    fig = _apply_base(fig, title)
    fig.update_layout(
        height=380,
        hovermode="x unified",
        xaxis_title="Years",
        yaxis_title="Portfolio value",
        yaxis_tickprefix="€",
        yaxis_tickformat=",.0f",
    )
    return fig


# ── Swensen drift bar chart ──────────────────────────────────────────────────

def build_drift_chart(
    positions: list,
    title: str = "Drift from target allocation",
) -> go.Figure:
    """Horizontal bar chart showing drift per asset class.

    Positive drift = overweight (red), negative = underweight (green).

    Args:
        positions: List of PortfolioPosition dataclasses.
        title: Chart title.
    """
    labels = [p.asset_class.value.replace("_", " ").title() for p in positions]
    drifts = [p.drift_pct for p in positions]
    colors = [_RED if d > 0 else _GREEN for d in drifts]
    threshold = 5.0

    fig = go.Figure(go.Bar(
        x=drifts,
        y=labels,
        orientation="h",
        marker_color=colors,
        marker_opacity=0.85,
        text=[f"{d:+.1f}pp" for d in drifts],
        textposition="outside",
        textfont=dict(size=11),
    ))

    # Threshold lines
    for xval in [threshold, -threshold]:
        fig.add_vline(
            x=xval,
            line=dict(color=_AMBER, width=1, dash="dot"),
        )

    fig = _apply_base(fig, title)
    fig.update_layout(
        height=280,
        xaxis_title="Drift (pp)",
        xaxis_zeroline=True,
        xaxis_zerolinecolor=_GRID,
        showlegend=False,
    )
    return fig


# Module-level constant used in components.py
_MUTED = "#6b7280"
