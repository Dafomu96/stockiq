"""Glossary page — every term explained with source references."""

from __future__ import annotations

import streamlit as st

from app.components import section_header
from app.i18n import t

_TERMS = [
    {
        "term_en": "CAPM — Capital Asset Pricing Model",
        "term_es": "CAPM — Modelo de Valoración de Activos",
        "body_en": (
            "r<sub>i</sub> = r<sub>f</sub> + β·(r<sub>m</sub> − r<sub>f</sub>). "
            "Determines the theoretically required annual return for an asset "
            "given its systematic risk (β). Higher β = more volatile = higher "
            "required return to compensate investors."
        ),
        "body_es": (
            "r<sub>i</sub> = r<sub>f</sub> + β·(r<sub>m</sub> − r<sub>f</sub>). "
            "Determina el retorno anual teóricamente requerido para un activo "
            "dado su riesgo sistemático (β). Mayor β = más volátil = mayor "
            "retorno exigido por los inversores."
        ),
        "source": "Sharpe (1964); Bodie, Kane, Marcus (2014) Investments, Ch.9",
        "category": "Fundamental",
    },
    {
        "term_en": "Beta (β)",
        "term_es": "Beta (β)",
        "body_en": (
            "β = Cov(r<sub>i</sub>, r<sub>m</sub>) / Var(r<sub>m</sub>). "
            "Measures systematic risk — how much an asset moves relative to "
            "the market. β=1: moves with market. β>1: more volatile. β<1: "
            "less volatile. β<0: moves opposite to market (rare)."
        ),
        "body_es": (
            "β = Cov(r<sub>i</sub>, r<sub>m</sub>) / Var(r<sub>m</sub>). "
            "Mide el riesgo sistemático — cuánto se mueve un activo respecto "
            "al mercado. β=1: se mueve igual que el mercado. β>1: más volátil. "
            "β<1: menos volátil."
        ),
        "source": "Bodie, Kane, Marcus (2014) Investments, Ch.9",
        "category": "Fundamental",
    },
    {
        "term_en": "Gordon Growth Model",
        "term_es": "Modelo de Gordon",
        "body_en": (
            "P = D / (r − g). Values a stock as the present value of a "
            "perpetually growing dividend stream. D = next year's dividend, "
            "r = required return (CAPM), g = perpetual growth rate. "
            "Requires g < r. Works best for mature dividend-paying companies."
        ),
        "body_es": (
            "P = D / (r − g). Valora una acción como el valor presente de "
            "un dividendo que crece en perpetuidad. D = dividendo del próximo año, "
            "r = retorno requerido (CAPM), g = tasa de crecimiento perpetuo. "
            "Requiere g < r. Funciona mejor para empresas maduras con dividendo."
        ),
        "source": "Gordon (1962); Shiller (2000) Irrational Exuberance",
        "category": "Fundamental",
    },
    {
        "term_en": "PDV — Present Discounted Value",
        "term_es": "VPD — Valor Presente Descontado",
        "body_en": (
            "PDV = CF / (1+r)ⁿ. The core concept of finance: a future cash "
            "flow is worth less today because of the time value of money. "
            "All asset valuation ultimately reduces to discounting future "
            "cash flows at an appropriate rate."
        ),
        "body_es": (
            "VPD = FC / (1+r)ⁿ. El concepto central de las finanzas: un flujo "
            "de caja futuro vale menos hoy por el valor temporal del dinero. "
            "Toda valoración de activos se reduce a descontar flujos futuros "
            "a una tasa apropiada."
        ),
        "source": "Shiller (2000) Market Volatility, Ch.3",
        "category": "Fundamental",
    },
    {
        "term_en": "RSI — Relative Strength Index",
        "term_es": "RSI — Índice de Fuerza Relativa",
        "body_en": (
            "Oscillator (0–100) measuring the speed and magnitude of price "
            "changes. RSI < 30 = oversold (potential buy). RSI > 70 = overbought "
            "(potential sell). Not a standalone signal — use with trend and volume."
        ),
        "body_es": (
            "Oscilador (0–100) que mide la velocidad y magnitud de los cambios "
            "de precio. RSI < 30 = sobrevendido (posible compra). RSI > 70 = "
            "sobrecomprado (posible venta). No es una señal autónoma: usar con "
            "tendencia y volumen."
        ),
        "source": "Murphy (1999) Technical Analysis, p.225",
        "category": "Technical",
    },
    {
        "term_en": "MACD — Moving Average Convergence/Divergence",
        "term_es": "MACD — Convergencia/Divergencia de Medias",
        "body_en": (
            "MACD line = EMA(12) − EMA(26). Signal line = EMA(9) of MACD. "
            "Histogram = MACD − signal. A bullish crossover (MACD crosses "
            "above signal) is a buy signal. Bearish crossover = sell signal."
        ),
        "body_es": (
            "Línea MACD = EMA(12) − EMA(26). Línea señal = EMA(9) del MACD. "
            "Histograma = MACD − señal. Un cruce alcista (MACD cruza por encima "
            "de la señal) es señal de compra. Cruce bajista = señal de venta."
        ),
        "source": "Murphy (1999) Technical Analysis, p.233",
        "category": "Technical",
    },
    {
        "term_en": "Bollinger Bands",
        "term_es": "Bandas de Bollinger",
        "body_en": (
            "Upper band = SMA(20) + 2σ. Lower band = SMA(20) − 2σ. "
            "Price touching the upper band signals potential overbought condition. "
            "Lower band signals potential oversold. %B measures position within bands."
        ),
        "body_es": (
            "Banda superior = SMA(20) + 2σ. Banda inferior = SMA(20) − 2σ. "
            "El precio tocando la banda superior señala posible sobrecompra. "
            "Banda inferior señala posible sobreventa. %B mide la posición dentro de las bandas."
        ),
        "source": "Murphy (1999) Technical Analysis, p.209",
        "category": "Technical",
    },
    {
        "term_en": "Golden Cross / Death Cross",
        "term_es": "Cruce Dorado / Cruz de la Muerte",
        "body_en": (
            "Golden Cross: SMA(50) crosses above SMA(200) — long-term bullish signal. "
            "Death Cross: SMA(50) crosses below SMA(200) — long-term bearish signal. "
            "The SMA(200) is the most widely watched long-term trend indicator."
        ),
        "body_es": (
            "Cruce Dorado: SMA(50) cruza por encima de SMA(200) — señal alcista a largo plazo. "
            "Cruz de la Muerte: SMA(50) cruza por debajo de SMA(200) — señal bajista. "
            "La SMA(200) es el indicador de tendencia a largo plazo más seguido."
        ),
        "source": "Murphy (1999) Technical Analysis, p.193–196",
        "category": "Technical",
    },
    {
        "term_en": "OBV — On-Balance Volume",
        "term_es": "OBV — Volumen en Balance",
        "body_en": (
            "OBV adds volume on up days and subtracts on down days. "
            "Rising OBV with rising price = volume confirms the trend. "
            "Divergence (OBV falling while price rises) = potential reversal warning."
        ),
        "body_es": (
            "El OBV suma el volumen en días alcistas y lo resta en bajistas. "
            "OBV creciente con precio creciente = el volumen confirma la tendencia. "
            "Divergencia (OBV cae mientras el precio sube) = posible señal de reversión."
        ),
        "source": "Murphy (1999) Technical Analysis, p.171",
        "category": "Technical",
    },
    {
        "term_en": "Swensen model allocation",
        "term_es": "Asignación del modelo Swensen",
        "body_en": (
            "30% domestic equity · 15% international equity · 5% emerging markets · "
            "20% real estate (REITs) · 15% government bonds · 15% TIPS. "
            "Designed for low cost, broad diversification, and low correlation between classes."
        ),
        "body_es": (
            "30% acciones domésticas · 15% acciones internacionales · 5% mercados emergentes · "
            "20% inmobiliario (REITs) · 15% bonos de gobierno · 15% TIPS. "
            "Diseñado para bajo coste, diversificación amplia y baja correlación entre clases."
        ),
        "source": "Swensen (2005) Unconventional Success, Appendix",
        "category": "Portfolio",
    },
    {
        "term_en": "Rebalancing",
        "term_es": "Rebalanceo",
        "body_en": (
            "Swensen's 5% rule: when any asset class drifts more than 5 percentage "
            "points from its target, sell what is overweight and buy what is underweight. "
            "This systematically buys low and sells high — without market timing."
        ),
        "body_es": (
            "Regla del 5% de Swensen: cuando una clase de activo se desvía más de 5 "
            "puntos porcentuales de su objetivo, vende lo que está por encima y compra "
            "lo que está por debajo. Esto compra barato y vende caro sistemáticamente."
        ),
        "source": "Swensen (2005) Unconventional Success, p.195",
        "category": "Portfolio",
    },
    {
        "term_en": "Sharpe Ratio",
        "term_es": "Ratio de Sharpe",
        "body_en": (
            "(Return − Risk-free rate) / Volatility. Measures return per unit of risk. "
            "> 1.0 = good risk-adjusted return. < 0 = underperforming the risk-free rate. "
            "Used to compare assets with different risk profiles."
        ),
        "body_es": (
            "(Retorno − Tasa libre de riesgo) / Volatilidad. Mide el retorno por unidad "
            "de riesgo. > 1.0 = buen retorno ajustado al riesgo. < 0 = rinde menos que "
            "el activo sin riesgo. Usado para comparar activos con distintos perfiles de riesgo."
        ),
        "source": "Sharpe (1994) The Sharpe Ratio, Journal of Portfolio Management",
        "category": "Risk",
    },
    {
        "term_en": "VaR — Value at Risk (95%)",
        "term_es": "VaR — Valor en Riesgo (95%)",
        "body_en": (
            "Parametric 1-year VaR at 95% confidence: "
            "base_rate − 1.645 × volatility. "
            "Interpretation: with 95% probability, the portfolio will not lose "
            "more than this fraction in a single year."
        ),
        "body_es": (
            "VaR paramétrico a 1 año con confianza del 95%: "
            "retorno_base − 1.645 × volatilidad. "
            "Interpretación: con un 95% de probabilidad, el portfolio no perderá "
            "más de esta fracción en un año."
        ),
        "source": "Bodie, Kane, Marcus (2014) Investments, Ch.5",
        "category": "Risk",
    },
]


def render() -> None:
    lang = st.session_state.get("lang", "en")
    section_header(t("glossary_title"), t("glossary_subtitle"))

    search = st.text_input(
        "", placeholder=t("glossary_search"), key="glossary_search"
    ).lower().strip()

    categories = ["All", "Fundamental", "Technical", "Portfolio", "Risk"]
    cat_filter = st.radio(
        "Category", categories, horizontal=True, key="glossary_cat"
    )

    # ── Filter terms ──────────────────────────────────────────────────────
    filtered = _TERMS
    if cat_filter != "All":
        filtered = [term for term in filtered if term["category"] == cat_filter]
    if search:
        filtered = [
            term for term in filtered
            if search in term[f"term_{lang}"].lower()
            or search in term[f"body_{lang}"].lower()
        ]

    st.markdown(
        f"<div style='font-size:12px;color:#4b5563;margin:8px 0;'>"
        f"{len(filtered)} terms</div>",
        unsafe_allow_html=True,
    )

    # ── Term cards ────────────────────────────────────────────────────────
    cat_colors = {
        "Fundamental": "#3b82f6",
        "Technical": "#8b5cf6",
        "Portfolio": "#10b981",
        "Risk": "#f59e0b",
    }

    for term in filtered:
        color = cat_colors.get(term["category"], "#6b7280")
        with st.expander(term[f"term_{lang}"], expanded=False):
            st.markdown(
                f"""
                <div style='margin-bottom:8px;'>
                    <span style='background:{color}18;color:{color};font-size:10px;
                                 font-weight:600;padding:2px 8px;border-radius:99px;'>
                        {term["category"]}
                    </span>
                </div>
                <div style='font-size:13px;color:#d1d5db;line-height:1.7;'>
                    {term[f"body_{lang}"]}
                </div>
                <div style='margin-top:10px;font-size:10px;color:#4b5563;
                             font-style:italic;'>
                    📚 {term["source"]}
                </div>
                """,
                unsafe_allow_html=True,
            )
