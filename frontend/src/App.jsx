import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAnalysis } from './hooks/useAnalysis'
import { useWatchlist } from './hooks/useWatchlist'
import { useHistory } from './hooks/useHistory'
import './lib/i18n'

import Overview    from './pages/Overview'
import Technical   from './pages/Technical'
import Fundamental from './pages/Fundamental'
import Portfolio   from './pages/Portfolio'
import Simulator   from './pages/Simulator'
import Glossary    from './pages/Glossary'
import Watchlist   from './pages/Watchlist'
import Compare from './pages/Compare'
import History from './pages/History'


const NAV = [
  { id: 'overview',    icon: '◈', label: 'Overview' },
  { id: 'technical',   icon: '⟁', label: 'Technical' },
  { id: 'fundamental', icon: '⊕', label: 'Fundamental' },
  { id: 'portfolio',   icon: '⬡', label: 'Portfolio' },
  { id: 'simulator',   icon: '◎', label: 'Simulator' },
  { id: 'watchlist',   icon: '★', label: 'Watchlist' },
  { id: 'glossary',    icon: '≡', label: 'Glossary' },
  { id: 'compare', icon: '⇌', label: 'Compare' },
  { id: 'history', icon: '◷', label: 'History' },
]

export default function App() {
  const { i18n } = useTranslation()
  const [page, setPage]   = useState('overview')
  const [input, setInput] = useState('')
  const { result, loading, error, run } = useAnalysis()
  const watchlist = useWatchlist()
  const history = useHistory()

  async function handleAnalyse(e) {
  e.preventDefault()
  if (!input.trim()) return
  const data = await run(input.trim())
  if (data) history.push(data)
}

  function toggleLang() {
    i18n.changeLanguage(i18n.language === 'en' ? 'es' : 'en')
  }

  // When a watchlist card triggers an analysis, navigate to overview
  function handleWatchlistAnalyse(data) {
    run(data.ticker)
    setPage('overview')
  }

  const currentTicker = result?.ticker ?? input.trim().toUpperCase()
  const isWatched = currentTicker ? watchlist.isWatched(currentTicker) : false

  return (
    <div style={{ display: 'flex', height: '100vh', background: '#040812', overflow: 'hidden' }}>

      {/* ── Sidebar ────────────────────────────────────────────────────── */}
      <aside style={{
        width: '200px',
        flexShrink: 0,
        background: '#080f1e',
        borderRight: '0.5px solid #1a2540',
        display: 'flex',
        flexDirection: 'column',
      }}>

        {/* Logo */}
        <div style={{ padding: '18px 18px 14px', borderBottom: '0.5px solid #1a2540' }}>
          <div style={{ fontFamily: 'Syne, sans-serif', fontSize: '18px', fontWeight: 700, color: '#f8fafc', letterSpacing: '-0.02em' }}>
            StockIQ
          </div>
          <div style={{ fontSize: '10px', color: '#2a3a5c', marginTop: '3px', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
            Shiller · Murphy · Swensen
          </div>
        </div>

        {/* Ticker input + analyse */}
        <form onSubmit={handleAnalyse} style={{ padding: '12px', borderBottom: '0.5px solid #1a2540' }}>
          <input
            value={input}
            onChange={e => setInput(e.target.value.toUpperCase())}
            placeholder="e.g. AAPL, ASML.AS"
            style={{
              width: '100%',
              background: '#040812',
              border: '0.5px solid #1a2540',
              borderRadius: '8px',
              padding: '7px 10px',
              fontSize: '12px',
              fontFamily: 'JetBrains Mono, monospace',
              color: '#e2e8f0',
              boxSizing: 'border-box',
            }}
          />

          {/* Analyse + watch row */}
          <div style={{ display: 'flex', gap: '6px', marginTop: '8px' }}>
            <button
              type="submit"
              disabled={loading || !input.trim()}
              style={{
                flex: 1,
                padding: '7px 0',
                fontSize: '12px',
                fontFamily: 'DM Sans, sans-serif',
                fontWeight: 500,
                background: loading ? '#1e3a5f' : '#3b82f6',
                border: 'none',
                borderRadius: '8px',
                color: '#fff',
                cursor: loading || !input.trim() ? 'not-allowed' : 'pointer',
                opacity: !input.trim() ? 0.4 : 1,
                transition: 'background 0.15s',
              }}
            >
              {loading ? '…' : 'Analyse'}
            </button>

            {/* Watch toggle — only show when there's a ticker to watch */}
            {currentTicker && (
              <button
                type="button"
                onClick={() => watchlist.toggle(currentTicker)}
                title={isWatched ? `Remove ${currentTicker} from watchlist` : `Add ${currentTicker} to watchlist`}
                style={{
                  padding: '7px 10px',
                  fontSize: '14px',
                  background: isWatched ? 'rgba(245,166,35,0.15)' : '#040812',
                  border: `0.5px solid ${isWatched ? '#f5a623' : '#1a2540'}`,
                  borderRadius: '8px',
                  color: isWatched ? '#f5a623' : '#4a5568',
                  cursor: 'pointer',
                  transition: 'all 0.15s',
                  lineHeight: 1,
                }}
              >
                {isWatched ? '★' : '☆'}
              </button>
            )}
          </div>
        </form>

        {/* Navigation */}
        <nav style={{ flex: 1, padding: '8px', overflowY: 'auto' }}>
          {NAV.map(item => {
            const isActive = page === item.id
            const isWatchlistItem = item.id === 'watchlist'
            return (
              <button
                key={item.id}
                onClick={() => setPage(item.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  width: '100%',
                  padding: '8px 10px',
                  marginBottom: '2px',
                  fontSize: '13px',
                  fontFamily: 'DM Sans, sans-serif',
                  background: isActive ? 'rgba(59,130,246,0.12)' : 'transparent',
                  border: isActive ? '0.5px solid rgba(59,130,246,0.3)' : '0.5px solid transparent',
                  borderLeft: isActive ? '2px solid #3b82f6' : '2px solid transparent',
                  borderRadius: '8px',
                  color: isActive ? '#93c5fd' : '#4a5568',
                  cursor: 'pointer',
                  textAlign: 'left',
                  transition: 'all 0.15s',
                }}
                onMouseEnter={e => { if (!isActive) e.currentTarget.style.color = '#94a3b8' }}
                onMouseLeave={e => { if (!isActive) e.currentTarget.style.color = '#4a5568' }}
              >
                <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '14px', width: '16px', textAlign: 'center', flexShrink: 0 }}>
                  {item.icon}
                </span>
                <span style={{ flex: 1 }}>{item.label}</span>
                {/* Watchlist badge */}
                {isWatchlistItem && watchlist.count > 0 && (
                  <span style={{
                    fontSize: '10px',
                    fontFamily: 'JetBrains Mono, monospace',
                    background: 'rgba(59,130,246,0.15)',
                    color: '#3b82f6',
                    padding: '1px 6px',
                    borderRadius: '99px',
                  }}>
                    {watchlist.count}
                  </span>
                )}
              </button>
            )
          })}
        </nav>

        {/* Footer */}
        <div style={{ padding: '10px 12px', borderTop: '0.5px solid #1a2540' }}>
          <button
            onClick={toggleLang}
            style={{
              width: '100%',
              padding: '6px 0',
              fontSize: '11px',
              fontFamily: 'DM Sans, sans-serif',
              background: 'transparent',
              border: '0.5px solid #1a2540',
              borderRadius: '8px',
              color: '#4a5568',
              cursor: 'pointer',
              marginBottom: '8px',
            }}
          >
            {i18n.language === 'en' ? '🇬🇧 EN → ES' : '🇪🇸 ES → EN'}
          </button>
          <p style={{ fontSize: '10px', color: '#1a2540', textAlign: 'center', lineHeight: 1.4, margin: 0 }}>
            Educational only · Not financial advice
          </p>
        </div>
      </aside>

      {/* ── Main content ────────────────────────────────────────────────── */}
      <main style={{ flex: 1, overflowY: 'auto' }}>
        <div style={{ maxWidth: '860px', margin: '0 auto', padding: '24px' }}>
          {page === 'overview'    && <Overview    result={result} loading={loading} error={error} />}
          {page === 'technical'   && <Technical   result={result} loading={loading} error={error} />}
          {page === 'fundamental' && <Fundamental result={result} loading={loading} error={error} />}
          {page === 'portfolio'   && <Portfolio />}
          {page === 'simulator'   && <Simulator   analysisResult={result} />}
          {page === 'watchlist'   && <Watchlist   watchlist={watchlist} onAnalyse={handleWatchlistAnalyse} />}
          {page === 'compare' && <Compare />}
          {page === 'history' && <History history={history} onReAnalyse={(ticker) => {
            setInput(ticker)
            run(ticker).then(data => { if (data) history.push(data) })
            setPage('overview')
          }} />}
          {page === 'glossary'    && <Glossary />}
        </div>
      </main>
    </div>
  )
}
