"""
StockIQ — Streamlit application entry point.

Run with:
    streamlit run app/streamlit_app.py

Architecture:
    - This file owns the sidebar, language toggle, ticker input,
      and session state initialisation.
    - Each page is a separate module in app/pages/ that exports a
      single render(result) function.
    - The analysis pipeline (fetch → fundamentals → technical → scoring)
      runs once per ticker and is cached in session_state to avoid
      redundant computation when switching pages.

Session state keys:
    lang          : "en" | "es"
    ticker        : last analysed ticker (uppercase)
    result        : CompositeResult | None
    fund_info     : dict from fetcher.get_fundamental_info()
    ohlcv_df      : pd.DataFrame with computed indicators
    swensen_result: SwensenPortfolioResult | None
    page          : active page name
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the project root is on sys.path regardless of how Streamlit is invoked
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from app.components import disclaimer_footer
from app.i18n import current_lang, set_language, t

# ── Page config (must be first Streamlit call) ───────────────────────────────

st.set_page_config(
    page_title="StockIQ",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ───────────────────────────────────────────────────────────────

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=JetBrains+Mono:wght@400;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'DM Sans', sans-serif;
        background-color: #0a0e1a;
        color: #e5e7eb;
    }
    .stApp { background-color: #0a0e1a; }
    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
    section[data-testid="stSidebar"] {
        background-color: #0f172a;
        border-right: 1px solid #1f2937;
    }
    section[data-testid="stSidebar"] .stButton button {
        width: 100%;
        text-align: left;
        background: transparent;
        border: none;
        color: #9ca3af;
        font-size: 14px;
        padding: 8px 12px;
        border-radius: 6px;
    }
    section[data-testid="stSidebar"] .stButton button:hover {
        background: #1e3a5f22;
        color: #f9fafb;
    }
    div[data-testid="metric-container"] {
        background: #111827;
        border: 1px solid #1f2937;
        border-radius: 10px;
        padding: 16px;
    }
    .stPlotlyChart { border-radius: 10px; overflow: hidden; }
    h1, h2, h3 { font-family: 'DM Sans', sans-serif; font-weight: 600; color: #f9fafb; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Session state initialisation ─────────────────────────────────────────────

_DEFAULTS: dict = {
    "lang": "en",
    "ticker": "",
    "result": None,
    "fund_info": None,
    "ohlcv_df": None,
    "swensen_result": None,
    "page": "overview",
}
for key, val in _DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    # Logo / app name
    st.markdown(
        """
        <div style="padding:12px 4px 20px;border-bottom:1px solid #1f2937;
                    margin-bottom:16px;">
            <div style="font-size:20px;font-weight:600;color:#f9fafb;
                        font-family:'DM Sans',sans-serif;">
                📈 StockIQ
            </div>
            <div style="font-size:11px;color:#4b5563;margin-top:3px;">
                Shiller · Murphy · Swensen
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Language toggle
    lang_col1, lang_col2 = st.columns(2)
    with lang_col1:
        if st.button("🇬🇧 EN", key="btn_en", use_container_width=True):
            set_language("en")
            st.rerun()
    with lang_col2:
        if st.button("🇪🇸 ES", key="btn_es", use_container_width=True):
            set_language("es")
            st.rerun()

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # Navigation
    pages = [
        ("overview",    "🏠", "nav_overview"),
        ("technical",   "📊", "nav_technical"),
        ("fundamental", "🏦", "nav_fundamental"),
        ("portfolio",   "🥧", "nav_portfolio"),
        ("simulator",   "🧮", "nav_simulator"),
        ("glossary",    "📖", "nav_glossary"),
    ]

    for page_id, icon, label_key in pages:
        is_active = st.session_state["page"] == page_id
        btn_label = f"{icon} {t(label_key)}"
        if is_active:
            st.markdown(
                f"""
                <div style="background:#1e3a5f;border-left:3px solid #3b82f6;
                            border-radius:6px;padding:8px 12px;margin-bottom:4px;
                            font-size:14px;color:#93c5fd;font-weight:500;">
                    {btn_label}
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            if st.button(btn_label, key=f"nav_{page_id}", use_container_width=True):
                st.session_state["page"] = page_id
                st.rerun()

    # Ticker input + analyse button
    st.markdown("<div style='height:20px;border-top:1px solid #1f2937;margin-top:12px'></div>", unsafe_allow_html=True)
    ticker_input = st.text_input(
        t("ticker_input_label"),
        value=st.session_state["ticker"],
        placeholder=t("ticker_input_placeholder"),
        help=t("ticker_input_help"),
        key="ticker_input_widget",
    ).strip().upper()

    analyse_clicked = st.button(
        t("analyze_btn"), key="analyze_btn",
        use_container_width=True, type="primary",
    )

# ── Analysis pipeline ─────────────────────────────────────────────────────────

if analyse_clicked and ticker_input:
    st.session_state["ticker"] = ticker_input
    st.session_state["result"] = None  # clear stale result
    st.session_state["fund_info"] = None
    st.session_state["ohlcv_df"] = None

    with st.spinner(t("analyzing_spinner")):
        try:
            from data.fetcher import MarketDataFetcher
            from analysis.fundamentals import compute_fundamental_score
            from analysis.technical import compute_technical_score
            from analysis.scoring import run_scoring

            fetcher = MarketDataFetcher()
            df = fetcher.get_ohlcv(ticker_input, period="1y")
            info = fetcher.get_fundamental_info(ticker_input)
            rf = fetcher.get_risk_free_rate()

            # Compute indicators onto the DataFrame for charting
            import pandas_ta as _ta  # noqa: F401
            df_ind = df.copy()
            df_ind.ta.rsi(length=14, append=True)
            df_ind.ta.macd(fast=12, slow=26, signal=9, append=True)
            df_ind.ta.bbands(length=20, std=2, append=True)
            df_ind.ta.sma(length=20, append=True)
            df_ind.ta.sma(length=50, append=True)
            df_ind.ta.sma(length=200, append=True)
            df_ind.ta.ema(length=20, append=True)
            df_ind.ta.obv(append=True)
            df_ind.ta.adx(length=14, append=True)

            current_price = info.get("regularMarketPrice") or float(df["Close"].iloc[-1])
            fundamental = compute_fundamental_score(
                current_price=current_price,
                beta=info.get("beta"),
                trailing_pe=info.get("trailingPE"),
                forward_pe=info.get("forwardPE"),
                dividend_rate=info.get("dividendRate"),
                dividend_yield=info.get("dividendYield"),
                earnings_growth=info.get("earningsGrowth"),
                risk_free_rate=rf,
            )
            technical = compute_technical_score(df)
            result = run_scoring(ticker_input, fundamental, technical)

            st.session_state["result"] = result
            st.session_state["fund_info"] = info
            st.session_state["ohlcv_df"] = df_ind

        except Exception as exc:
            from config.exceptions import InvalidTickerError, InsufficientDataError
            if isinstance(exc, InvalidTickerError):
                st.error(t("error_invalid_ticker"))
            elif isinstance(exc, InsufficientDataError):
                st.error(t("error_insufficient_data"))
            else:
                st.error(f"{t('error_generic')}: {exc}")

# ── Page routing ──────────────────────────────────────────────────────────────

page = st.session_state["page"]
result = st.session_state.get("result")
info = st.session_state.get("fund_info")
df_ind = st.session_state.get("ohlcv_df")

if page == "overview":
    from app.pages import overview
    overview.render(result, info, df_ind)

elif page == "technical":
    from app.pages import technical
    technical.render(result, df_ind)

elif page == "fundamental":
    from app.pages import fundamental
    fundamental.render(result, info)

elif page == "portfolio":
    from app.pages import portfolio
    portfolio.render()

elif page == "simulator":
    from app.pages import simulator
    simulator.render(result)

elif page == "glossary":
    from app.pages import glossary
    glossary.render()

# ── Footer ────────────────────────────────────────────────────────────────────

disclaimer_footer()
