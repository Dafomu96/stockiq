/**
 * Compare page — side-by-side analysis of two tickers.
 *
 * Calls POST /v1/compare and renders:
 *   - Ticker input pair
 *   - Head-to-head verdict banner
 *   - Side-by-side score cards (composite, fundamental, technical)
 *   - Metric comparison table (CAPM, Gordon, P/E, RSI, MA)
 *   - Winner explanation
 */

import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { SignalBadge, ScoreBar, ExplainBox, Spinner, scoreColor } from '../components/ui'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function compareRequest(tickerA, tickerB) {
  const res = await fetch(`${BASE_URL}/v1/compare`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ticker_a: tickerA, ticker_b: tickerB }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw { status: res.status, message: body.detail ?? `HTTP ${res.status}` }
  }
  return res.json()
}

// ── Metric row ────────────────────────────────────────────────────────────────

function MetricRow({ label, valueA, valueB, higherIsBetter = true, format = v => v ?? '—' }) {
  const a = valueA != null ? parseFloat(valueA) : null
  const b = valueB != null ? parseFloat(valueB) : null

  let colorA = 'var(--color-text-primary)'
  let colorB = 'var(--color-text-primary)'

  if (a != null && b != null && a !== b) {
    const aWins = higherIsBetter ? a > b : a < b
    colorA = aWins ? '#00d97e' : '#ff4757'
    colorB = aWins ? '#ff4757' : '#00d97e'
  }

  return (
    <tr style={{ borderBottom: '0.5px solid var(--color-border-tertiary)' }}>
      <td style={{ padding: '8px 12px', fontSize: '12px', color: 'var(--color-text-secondary)', fontFamily: 'var(--font-sans)' }}>
        {label}
      </td>
      <td style={{ padding: '8px 12px', fontSize: '12px', fontFamily: 'var(--font-mono)', color: colorA, textAlign: 'right', fontWeight: 500 }}>
        {format(valueA)}
      </td>
      <td style={{ padding: '8px 12px', fontSize: '12px', fontFamily: 'var(--font-mono)', color: colorB, textAlign: 'right', fontWeight: 500 }}>
        {format(valueB)}
      </td>
    </tr>
  )
}

// ── Score column ──────────────────────────────────────────────────────────────

function ScoreColumn({ summary, isWinner }) {
  const borderColor = isWinner ? '#00d97e' : 'var(--color-border-tertiary)'
  const borderWidth = isWinner ? '2px' : '0.5px'

  return (
    <div style={{
      background: 'var(--color-background-primary)',
      border: `${borderWidth} solid ${borderColor}`,
      borderRadius: 'var(--border-radius-lg)',
      padding: '20px',
      flex: 1,
      position: 'relative',
    }}>
      {isWinner && (
        <div style={{
          position: 'absolute',
          top: '-10px',
          left: '50%',
          transform: 'translateX(-50%)',
          background: '#00d97e',
          color: '#040812',
          fontSize: '10px',
          fontWeight: 700,
          padding: '2px 10px',
          borderRadius: '99px',
          letterSpacing: '0.08em',
          whiteSpace: 'nowrap',
        }}>
          HIGHER SCORE
        </div>
      )}

      <div style={{
        fontFamily: 'var(--font-mono)',
        fontSize: '22px',
        fontWeight: 700,
        color: 'var(--color-text-primary)',
        marginBottom: '4px',
      }}>
        {summary.ticker}
      </div>

      <div style={{ marginBottom: '16px' }}>
        <SignalBadge signal={summary.signal} score={summary.composite_score} />
      </div>

      <ScoreBar label="Fundamental" value={summary.fundamental_score} color="#3b82f6" />
      <ScoreBar label="Technical"   value={summary.technical_score}   color="#8b5cf6" />
      <ScoreBar
        label="Composite"
        value={summary.composite_score}
        color={scoreColor(summary.composite_score)}
      />

      <div style={{ marginTop: '12px', fontSize: '11px', color: 'var(--color-text-secondary)', fontFamily: 'var(--font-sans)' }}>
        Confidence: <span style={{ color: { high: '#00d97e', medium: '#f5a623', low: '#ff4757' }[summary.confidence] }}>
          {summary.confidence}
        </span>
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function Compare() {
  const { t } = useTranslation()
  const [tickerA, setTickerA] = useState('')
  const [tickerB, setTickerB] = useState('')
  const [result,  setResult]  = useState(null)
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState(null)

  async function run(e) {
    e.preventDefault()
    const a = tickerA.trim().toUpperCase()
    const b = tickerB.trim().toUpperCase()
    if (!a || !b || a === b) return

    setLoading(true)
    setError(null)
    try {
      const data = await compareRequest(a, b)
      setResult(data)
    } catch (err) {
      setError(err)
    } finally {
      setLoading(false)
    }
  }

  const fmt = {
    pct:   v => v != null ? `${(v * 100).toFixed(1)}%` : '—',
    price: v => v != null ? v.toFixed(2) : '—',
    score: v => v != null ? v.toFixed(1) : '—',
    str:   v => v != null ? String(v).replace(/_/g, ' ') : '—',
    bool:  v => v ? 'Yes ✓' : 'No',
  }

  return (
    <div style={{ paddingTop: '1rem' }}>

      {/* Header */}
      <h1 style={{ fontSize: '22px', fontWeight: 500, color: 'var(--color-text-primary)', marginBottom: '4px' }}>
        Compare
      </h1>
      <p style={{ fontSize: '13px', color: 'var(--color-text-secondary)', marginBottom: '24px' }}>
        Side-by-side Shiller + Murphy analysis for two tickers
      </p>

      {/* Input form */}
      <form onSubmit={run} style={{ display: 'flex', gap: '8px', alignItems: 'flex-end', flexWrap: 'wrap', marginBottom: '28px' }}>
        <div>
          <label style={{ display: 'block', fontSize: '11px', color: 'var(--color-text-secondary)', marginBottom: '4px' }}>
            Ticker A
          </label>
          <input
            value={tickerA}
            onChange={e => setTickerA(e.target.value.toUpperCase())}
            placeholder="e.g. AAPL"
            style={{ width: '140px' }}
          />
        </div>

        <div style={{ fontSize: '18px', color: 'var(--color-text-secondary)', paddingBottom: '6px' }}>vs</div>

        <div>
          <label style={{ display: 'block', fontSize: '11px', color: 'var(--color-text-secondary)', marginBottom: '4px' }}>
            Ticker B
          </label>
          <input
            value={tickerB}
            onChange={e => setTickerB(e.target.value.toUpperCase())}
            placeholder="e.g. MSFT"
            style={{ width: '140px' }}
          />
        </div>

        <button
          type="submit"
          disabled={loading || !tickerA.trim() || !tickerB.trim() || tickerA === tickerB}
          style={{ marginBottom: '1px' }}
        >
          {loading ? 'Analysing…' : 'Compare ↗'}
        </button>
      </form>

      {tickerA && tickerB && tickerA.trim().toUpperCase() === tickerB.trim().toUpperCase() && (
        <p style={{ fontSize: '12px', color: '#ff4757', marginBottom: '16px' }}>
          Tickers must be different.
        </p>
      )}

      {loading && <Spinner />}

      {error && (
        <div style={{
          background: 'rgba(255,71,87,0.08)',
          border: '0.5px solid rgba(255,71,87,0.3)',
          borderRadius: 'var(--border-radius-md)',
          padding: '12px 16px',
          fontSize: '13px',
          color: '#ff4757',
          marginBottom: '20px',
        }}>
          {error.message}
        </div>
      )}

      {result && !loading && (
        <>
          {/* Verdict banner */}
          <div style={{
            background: result.verdict.is_tied
              ? 'rgba(245,166,35,0.08)'
              : 'rgba(0,217,126,0.08)',
            border: `0.5px solid ${result.verdict.is_tied ? 'rgba(245,166,35,0.3)' : 'rgba(0,217,126,0.3)'}`,
            borderRadius: 'var(--border-radius-lg)',
            padding: '16px 20px',
            marginBottom: '20px',
          }}>
            <div style={{
              fontSize: '13px',
              fontWeight: 500,
              color: result.verdict.is_tied ? '#f5a623' : '#00d97e',
              marginBottom: '6px',
              fontFamily: 'var(--font-sans)',
            }}>
              {result.verdict.is_tied
                ? '⚖ Too close to call'
                : `★ ${result.verdict.winner} scores higher by ${result.verdict.margin.toFixed(1)} points`
              }
            </div>
            <p style={{ fontSize: '12px', color: 'var(--color-text-secondary)', margin: 0, lineHeight: 1.5, fontFamily: 'var(--font-sans)' }}>
              {result.verdict.reason}
            </p>
            {(result.verdict.fundamental_winner || result.verdict.technical_winner) && (
              <div style={{ display: 'flex', gap: '16px', marginTop: '10px' }}>
                {result.verdict.fundamental_winner && (
                  <span style={{ fontSize: '11px', color: '#3b82f6' }}>
                    Fundamental winner: <strong>{result.verdict.fundamental_winner}</strong>
                  </span>
                )}
                {result.verdict.technical_winner && (
                  <span style={{ fontSize: '11px', color: '#8b5cf6' }}>
                    Technical winner: <strong>{result.verdict.technical_winner}</strong>
                  </span>
                )}
              </div>
            )}
          </div>

          {/* Score columns */}
          <div style={{ display: 'flex', gap: '16px', marginBottom: '24px' }}>
            <ScoreColumn
              summary={result.ticker_a}
              isWinner={result.verdict.winner === result.ticker_a.ticker}
            />
            <ScoreColumn
              summary={result.ticker_b}
              isWinner={result.verdict.winner === result.ticker_b.ticker}
            />
          </div>

          {/* Metric comparison table */}
          <div style={{
            background: 'var(--color-background-primary)',
            border: '0.5px solid var(--color-border-tertiary)',
            borderRadius: 'var(--border-radius-lg)',
            overflow: 'hidden',
            marginBottom: '20px',
          }}>
            <div style={{ padding: '14px 16px', borderBottom: '0.5px solid var(--color-border-tertiary)' }}>
              <span style={{ fontSize: '13px', fontWeight: 500, color: 'var(--color-text-primary)' }}>
                Metric comparison
              </span>
              <span style={{ fontSize: '11px', color: 'var(--color-text-secondary)', marginLeft: '8px' }}>
                green = better value for that metric
              </span>
            </div>

            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: 'var(--color-background-secondary)' }}>
                  <th style={{ padding: '8px 12px', fontSize: '11px', color: 'var(--color-text-secondary)', textAlign: 'left', fontWeight: 500 }}>
                    Metric
                  </th>
                  <th style={{ padding: '8px 12px', fontSize: '11px', color: '#3b82f6', textAlign: 'right', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                    {result.ticker_a.ticker}
                  </th>
                  <th style={{ padding: '8px 12px', fontSize: '11px', color: '#8b5cf6', textAlign: 'right', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                    {result.ticker_b.ticker}
                  </th>
                </tr>
              </thead>
              <tbody>
                <MetricRow label="Composite score"    valueA={result.ticker_a.composite_score}  valueB={result.ticker_b.composite_score}  format={fmt.score} />
                <MetricRow label="Fundamental score"  valueA={result.ticker_a.fundamental_score} valueB={result.ticker_b.fundamental_score} format={fmt.score} />
                <MetricRow label="Technical score"    valueA={result.ticker_a.technical_score}   valueB={result.ticker_b.technical_score}   format={fmt.score} />
                <MetricRow label="CAPM required return" valueA={result.ticker_a.capm_return}  valueB={result.ticker_b.capm_return}  higherIsBetter={false} format={fmt.pct} />
                <MetricRow label="Beta (β)"           valueA={result.ticker_a.beta}           valueB={result.ticker_b.beta}           higherIsBetter={false} format={v => v != null ? v.toFixed(2) : '—'} />
                <MetricRow label="Gordon upside"      valueA={result.ticker_a.upside_pct}     valueB={result.ticker_b.upside_pct}     format={v => v != null ? `${v.toFixed(1)}%` : '—'} />
                <MetricRow label="P/E (actual)"       valueA={result.ticker_a.pe_actual}      valueB={result.ticker_b.pe_actual}      higherIsBetter={false} format={v => v != null ? v.toFixed(1) : '—'} />
                <MetricRow label="P/E interpretation" valueA={result.ticker_a.pe_interpretation} valueB={result.ticker_b.pe_interpretation} format={fmt.str} />
                <MetricRow label="RSI (14)"           valueA={result.ticker_a.rsi_value}      valueB={result.ticker_b.rsi_value}      format={v => v != null ? v.toFixed(1) : '—'} />
                <MetricRow label="Golden Cross"       valueA={result.ticker_a.golden_cross}   valueB={result.ticker_b.golden_cross}   format={fmt.bool} />
                <MetricRow label="Price above SMA200" valueA={result.ticker_a.price_above_sma200} valueB={result.ticker_b.price_above_sma200} format={fmt.bool} />
              </tbody>
            </table>
          </div>

          <ExplainBox
            title="How to read this comparison"
            source="Shiller (2000); Murphy (1999); Bodie et al. (2014)"
          >
            Green values indicate a better reading for that metric. For CAPM return and Beta,
            lower is better (less risk required). For P/E, lower usually means cheaper relative
            to earnings. For Gordon upside, positive means the stock trades below intrinsic value.
            The composite score weighs fundamental (Shiller) and technical (Murphy) signals equally.
            A higher score does not guarantee better returns — it reflects the model's assessment
            at this point in time with available data.
          </ExplainBox>

          <p style={{ fontSize: '10px', color: 'var(--color-text-secondary)', marginTop: '16px', fontFamily: 'var(--font-sans)' }}>
            {result.disclaimer} · Analysis as of {result.analysed_at.slice(0, 10)}
          </p>
        </>
      )}
    </div>
  )
}
