/**
 * Watchlist page — shows saved tickers with their last known scores.
 *
 * Each ticker card displays:
 *   - Ticker symbol + signal badge
 *   - Composite score bar
 *   - Fundamental / technical sub-scores
 *   - "Analyse" button to run a fresh analysis
 *   - Remove button
 *
 * Scores are cached in localStorage keyed by ticker so the page is
 * useful even without re-running analysis. On first visit with no
 * cached scores, cards show a "Not analysed yet" state.
 *
 * localStorage key format:
 *   "stockiq:score:<TICKER>" → { score, signal, fundamental, technical, ts }
 */

import { useState, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { analyze } from '../lib/api'
import {
  SignalBadge, ScoreBar, EmptyState, scoreColor,
} from '../components/ui'

const SCORE_KEY = (ticker) => `stockiq:score:${ticker}`

function loadScore(ticker) {
  try {
    const raw = localStorage.getItem(SCORE_KEY(ticker))
    return raw ? JSON.parse(raw) : null
  } catch { return null }
}

function saveScore(ticker, data) {
  try {
    localStorage.setItem(SCORE_KEY(ticker), JSON.stringify({
      score: data.composite_score,
      signal: data.signal,
      fundamental: data.score_breakdown?.fundamental,
      technical: data.score_breakdown?.technical,
      ts: new Date().toISOString().slice(0, 10),
    }))
  } catch {}
}

// ── Ticker card ───────────────────────────────────────────────────────────────

function TickerCard({ ticker, onRemove, onAnalyse }) {
  const [cached, setCached] = useState(() => loadScore(ticker))
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const runAnalysis = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await analyze(ticker)
      saveScore(ticker, data)
      setCached(loadScore(ticker))
      onAnalyse(data)
    } catch (err) {
      setError(err.message ?? 'Error')
    } finally {
      setLoading(false)
    }
  }, [ticker, onAnalyse])

  const signalBg = {
    buy: 'rgba(0,217,126,0.06)',
    sell: 'rgba(255,71,87,0.06)',
    neutral: 'rgba(245,166,35,0.06)',
  }[cached?.signal] ?? 'transparent'

  return (
    <div style={{
      background: signalBg,
      border: '0.5px solid var(--color-border-tertiary)',
      borderRadius: 'var(--border-radius-lg)',
      padding: '16px',
      display: 'flex',
      flexDirection: 'column',
      gap: '12px',
    }}>

      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '8px' }}>
        <div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '18px', fontWeight: 600, color: 'var(--color-text-primary)' }}>
            {ticker}
          </div>
          {cached?.ts && (
            <div style={{ fontSize: '11px', color: 'var(--color-text-secondary)', marginTop: '2px' }}>
              Last analysed: {cached.ts}
            </div>
          )}
        </div>
        <button
          onClick={() => onRemove(ticker)}
          aria-label={`Remove ${ticker} from watchlist`}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            color: 'var(--color-text-secondary)',
            padding: '4px',
            fontSize: '16px',
            lineHeight: 1,
            borderRadius: 'var(--border-radius-md)',
          }}
        >
          <i className="ti ti-x" aria-hidden="true" />
        </button>
      </div>

      {/* Score content */}
      {cached ? (
        <>
          <SignalBadge signal={cached.signal} score={cached.score} />
          <div>
            <ScoreBar
              label="Fundamental"
              value={cached.fundamental}
              color="#3b82f6"
            />
            <ScoreBar
              label="Technical"
              value={cached.technical}
              color="#8b5cf6"
            />
            <ScoreBar
              label="Composite"
              value={cached.score}
              color={scoreColor(cached.score)}
            />
          </div>
        </>
      ) : (
        <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', fontStyle: 'italic' }}>
          Not analysed yet — run analysis to see scores.
        </div>
      )}

      {/* Error */}
      {error && (
        <div style={{ fontSize: '11px', color: '#ff4757', background: 'rgba(255,71,87,0.08)', borderRadius: 'var(--border-radius-md)', padding: '6px 10px' }}>
          {error}
        </div>
      )}

      {/* Actions */}
      <button
        onClick={runAnalysis}
        disabled={loading}
        style={{
          width: '100%',
          padding: '8px',
          fontSize: '12px',
          fontFamily: 'var(--font-sans)',
          fontWeight: 500,
          background: 'var(--color-background-secondary)',
          border: '0.5px solid var(--color-border-secondary)',
          borderRadius: 'var(--border-radius-md)',
          color: 'var(--color-text-primary)',
          cursor: loading ? 'not-allowed' : 'pointer',
          opacity: loading ? 0.5 : 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '6px',
          transition: 'background 0.15s',
        }}
      >
        {loading ? (
          <>
            <span style={{
              width: '12px', height: '12px', borderRadius: '50%',
              border: '1.5px solid var(--color-text-secondary)',
              borderTopColor: 'transparent',
              display: 'inline-block',
              animation: 'spin 0.7s linear infinite',
            }} />
            Analysing…
          </>
        ) : (
          <>
            <i className="ti ti-refresh" aria-hidden="true" style={{ fontSize: '14px' }} />
            {cached ? 'Refresh analysis' : 'Run analysis'}
          </>
        )}
      </button>
    </div>
  )
}

// ── Watchlist page ─────────────────────────────────────────────────────────────

export default function Watchlist({ watchlist, onAnalyse }) {
  const { t } = useTranslation()
  const { tickers, add, remove, isFull } = watchlist
  const [input, setInput] = useState('')

  function handleAdd(e) {
    e.preventDefault()
    const val = input.trim().toUpperCase()
    if (val) {
      add(val)
      setInput('')
    }
  }

  if (tickers.length === 0) {
    return (
      <div style={{ paddingTop: '1rem' }}>
        <h1 style={{ fontSize: '22px', fontWeight: 500, color: 'var(--color-text-primary)', marginBottom: '4px' }}>
          Watchlist
        </h1>
        <p style={{ fontSize: '13px', color: 'var(--color-text-secondary)', marginBottom: '24px' }}>
          Save tickers to track and re-analyse quickly.
        </p>

        {/* Add form */}
        <form onSubmit={handleAdd} style={{ display: 'flex', gap: '8px', marginBottom: '32px' }}>
          <input
            value={input}
            onChange={e => setInput(e.target.value.toUpperCase())}
            placeholder="e.g. AAPL, ASML.AS"
            style={{ flex: 1, maxWidth: '240px' }}
          />
          <button type="submit" disabled={!input.trim()}>
            Add ticker
          </button>
        </form>

        <EmptyState message="Your watchlist is empty. Add a ticker above to start tracking." />
      </div>
    )
  }

  return (
    <div style={{ paddingTop: '1rem' }}>
      <h1 style={{ fontSize: '22px', fontWeight: 500, color: 'var(--color-text-primary)', marginBottom: '4px' }}>
        Watchlist
      </h1>
      <p style={{ fontSize: '13px', color: 'var(--color-text-secondary)', marginBottom: '20px' }}>
        {tickers.length} ticker{tickers.length !== 1 ? 's' : ''} saved
        {isFull && ' · limit reached (20 max)'}
      </p>

      {/* Add form */}
      {!isFull && (
        <form onSubmit={handleAdd} style={{ display: 'flex', gap: '8px', marginBottom: '20px' }}>
          <input
            value={input}
            onChange={e => setInput(e.target.value.toUpperCase())}
            placeholder="Add ticker…"
            style={{ flex: 1, maxWidth: '200px' }}
          />
          <button type="submit" disabled={!input.trim()}>
            Add
          </button>
        </form>
      )}

      {/* Ticker grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: '12px',
      }}>
        {tickers.map(ticker => (
          <TickerCard
            key={ticker}
            ticker={ticker}
            onRemove={remove}
            onAnalyse={onAnalyse}
          />
        ))}
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  )
}
