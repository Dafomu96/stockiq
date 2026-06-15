import { useState } from 'react'
import { useTranslation } from 'react-i18next'

const TERMS = [
  {
    term: { en: 'CAPM — Capital Asset Pricing Model', es: 'CAPM — Modelo de Valoración de Activos' },
    body: {
      en: 'r = rf + β·(rm − rf). Determines the theoretically required annual return for an asset given its systematic risk. Higher β = more volatile = higher required return.',
      es: 'r = rf + β·(rm − rf). Determina el retorno anual teórico para un activo dado su riesgo sistemático. Mayor β = más volátil = mayor retorno exigido.',
    },
    source: 'Sharpe (1964); Bodie, Kane, Marcus (2014) Investments, Ch.9',
    category: 'Fundamental',
  },
  {
    term: { en: 'Beta (β)', es: 'Beta (β)' },
    body: {
      en: 'Cov(ri, rm) / Var(rm). Measures systematic risk vs the market. β=1 moves with market. β>1 more volatile. β<1 less volatile.',
      es: 'Cov(ri, rm) / Var(rm). Mide el riesgo sistemático respecto al mercado. β=1 se mueve igual. β>1 más volátil. β<1 menos volátil.',
    },
    source: 'Bodie, Kane, Marcus (2014) Investments, Ch.9',
    category: 'Fundamental',
  },
  {
    term: { en: 'Gordon Growth Model', es: 'Modelo de Gordon' },
    body: {
      en: 'P = D/(r−g). Values a stock as the present value of perpetually growing dividends. Requires g < r. Best for mature dividend-paying companies.',
      es: 'P = D/(r−g). Valora una acción como el valor presente de dividendos crecientes en perpetuidad. Requiere g < r. Funciona para empresas maduras con dividendo.',
    },
    source: 'Gordon (1962); Shiller (2000) Irrational Exuberance',
    category: 'Fundamental',
  },
  {
    term: { en: 'RSI — Relative Strength Index', es: 'RSI — Índice de Fuerza Relativa' },
    body: {
      en: 'Oscillator 0–100 measuring momentum. Below 30 = oversold (potential buy). Above 70 = overbought (potential sell). Neutral zone 30–70.',
      es: 'Oscilador 0–100 que mide momentum. Por debajo de 30 = sobrevendido (compra). Por encima de 70 = sobrecomprado (venta). Zona neutra 30–70.',
    },
    source: 'Murphy (1999) Technical Analysis, p.225',
    category: 'Technical',
  },
  {
    term: { en: 'MACD', es: 'MACD' },
    body: {
      en: 'EMA(12) − EMA(26). Bullish crossover (MACD above signal line) = rising momentum. Bearish crossover = falling momentum.',
      es: 'EMA(12) − EMA(26). Cruce alcista (MACD por encima de señal) = momentum creciente. Cruce bajista = momentum decreciente.',
    },
    source: 'Murphy (1999) Technical Analysis, p.233',
    category: 'Technical',
  },
  {
    term: { en: 'Golden Cross / Death Cross', es: 'Cruce Dorado / Cruz de la Muerte' },
    body: {
      en: 'Golden Cross: SMA50 above SMA200 = long-term bullish. Death Cross: SMA50 below SMA200 = long-term bearish. Most watched long-term trend signals.',
      es: 'Cruce Dorado: SMA50 por encima de SMA200 = alcista largo plazo. Cruz de la Muerte: SMA50 por debajo = bajista. Las señales de tendencia más seguidas.',
    },
    source: 'Murphy (1999) Technical Analysis, p.193–196',
    category: 'Technical',
  },
  {
    term: { en: 'Swensen model allocation', es: 'Asignación modelo Swensen' },
    body: {
      en: '30% domestic equity · 15% international · 5% emerging · 20% REITs · 15% bonds · 15% TIPS. Low cost, diversified, low correlation between classes.',
      es: '30% renta variable USA · 15% internacional · 5% emergentes · 20% REITs · 15% bonos · 15% TIPS. Bajo coste, diversificado, baja correlación entre clases.',
    },
    source: 'Swensen (2005) Unconventional Success, Appendix',
    category: 'Portfolio',
  },
  {
    term: { en: 'Rebalancing', es: 'Rebalanceo' },
    body: {
      en: "5% rule: when any asset class drifts >5pp from target, sell the overweight and buy the underweight. Systematically buys low and sells high without market timing.",
      es: 'Regla del 5%: cuando una clase se desvía > 5pp del objetivo, vende lo que sobra y compra lo que falta. Compra barato y vende caro sistemáticamente.',
    },
    source: 'Swensen (2005) Unconventional Success, p.195',
    category: 'Portfolio',
  },
  {
    term: { en: 'Sharpe Ratio', es: 'Ratio de Sharpe' },
    body: {
      en: '(Return − Risk-free rate) / Volatility. Measures return per unit of risk. > 1.0 is generally considered good. Used to compare assets with different risk profiles.',
      es: '(Retorno − Tasa libre de riesgo) / Volatilidad. Mide el retorno por unidad de riesgo. > 1.0 se considera bueno. Compara activos con distintos perfiles de riesgo.',
    },
    source: 'Sharpe (1994) The Sharpe Ratio, Journal of Portfolio Management',
    category: 'Risk',
  },
  {
    term: { en: 'VaR — Value at Risk (95%)', es: 'VaR — Valor en Riesgo (95%)' },
    body: {
      en: 'Parametric 1-year VaR: base_rate − 1.645 × volatility. With 95% confidence, the portfolio will not lose more than this fraction in a single year.',
      es: 'VaR paramétrico 1 año: retorno_base − 1.645 × volatilidad. Con 95% de probabilidad, el portfolio no perderá más de esta fracción en un año.',
    },
    source: 'Bodie, Kane, Marcus (2014) Investments, Ch.5',
    category: 'Risk',
  },
]

const CATEGORY_COLORS = {
  Fundamental: { text: '#3b82f6', bg: 'rgba(59,130,246,0.1)' },
  Technical:   { text: '#8b5cf6', bg: 'rgba(139,92,246,0.1)' },
  Portfolio:   { text: '#00d97e', bg: 'rgba(0,217,126,0.1)' },
  Risk:        { text: '#f5a623', bg: 'rgba(245,166,35,0.1)' },
}

export default function Glossary() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language

  const [search, setSearch]     = useState('')
  const [category, setCategory] = useState('All')

  const filtered = TERMS.filter(term => {
    const matchCat  = category === 'All' || term.category === category
    const matchSearch = !search || (
      term.term[lang]?.toLowerCase().includes(search.toLowerCase()) ||
      term.body[lang]?.toLowerCase().includes(search.toLowerCase())
    )
    return matchCat && matchSearch
  })

  const categories = ['All', 'Fundamental', 'Technical', 'Portfolio', 'Risk']

  return (
    <div className="page-enter space-y-5">

      <div>
        <h1 className="text-2xl font-display font-bold text-slate-100">{t('glossary_title')}</h1>
        <p className="text-xs text-slate-500 mt-0.5 font-body">
          Every term explained with its source reference
        </p>
      </div>

      {/* ── Search + filter ── */}
      <div className="flex flex-col sm:flex-row gap-3">
        <input
          type="text"
          placeholder={t('glossary_search')}
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="flex-1 bg-bg-secondary border border-bg-border rounded-lg px-3 py-2 text-sm font-body text-slate-200 focus:outline-none focus:border-accent placeholder-slate-600"
        />
        <div className="flex gap-1.5 flex-wrap">
          {categories.map(cat => (
            <button
              key={cat}
              onClick={() => setCategory(cat)}
              className={`px-3 py-1.5 text-xs rounded-lg font-body transition-colors ${
                category === cat
                  ? 'bg-accent text-white'
                  : 'btn-ghost'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      <p className="text-[11px] text-slate-600 font-body">{filtered.length} terms</p>

      {/* ── Terms ── */}
      <div className="space-y-2">
        {filtered.map((term, i) => {
          const c = CATEGORY_COLORS[term.category]
          return (
            <details key={i} className="card group">
              <summary className="flex items-center justify-between cursor-pointer select-none list-none">
                <span className="text-sm font-body font-medium text-slate-200 group-hover:text-slate-100 transition-colors">
                  {term.term[lang] ?? term.term.en}
                </span>
                <span
                  className="text-[10px] font-semibold px-2 py-0.5 rounded-full flex-shrink-0"
                  style={{ color: c.text, background: c.bg }}
                >
                  {term.category}
                </span>
              </summary>
              <div className="mt-3 pt-3 border-t border-bg-border">
                <p className="text-sm text-slate-400 font-body leading-relaxed">
                  {term.body[lang] ?? term.body.en}
                </p>
                <p className="text-[10px] text-slate-600 font-body mt-2 italic">
                  📚 {term.source}
                </p>
              </div>
            </details>
          )
        })}
      </div>
    </div>
  )
}
