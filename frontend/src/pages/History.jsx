/**
 * History page — chronological list of past analyses.
 *
 * Shows ticker, date/time, composite score bar, signal badge,
 * sub-scores, and a re-analyse button per entry.
 * Entries are stored in localStorage via useHistory.
 */

import { EmptyState, SignalBadge, ScoreBar, scoreColor } from '../components/ui'

const confColor = { high: '#00d97e', medium: '#f5a623', low: '#ff4757' }

function HistoryRow({ entry, onReAnalyse, onRemove }) {
  return (
    <div style={{
      background: 'var(--color-background-primary)',
      border: '0.5px solid var(--color-border-tertiary)',
      borderRadius: 'var(--border-radius-lg)',
      padding: '16px',
      display: 'grid',
      gridTemplateColumns: '1fr auto',
      gap: '16px',
      alignItems: 'start',
    }}>

      {/* Left — ticker + scores */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '10px', flexWrap: 'wrap' }}>
          <span style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '16px',
            fontWeight: 600,
            color: 'var(--color-text-primary)',
          }}>
            {entry.ticker}
          </span>
          <SignalBadge signal={entry.signal} score={entry.score} />
          <span style={{ fontSize: '11px', color: 'var(--color-text-secondary)' }}>
            {entry.date} · {entry.time}
          </span>
          {entry.confidence && (
            <span style={{
              fontSize: '10px',
              color: confColor[entry.confidence] ?? 'var(--color-text-secondary)',
            }}>
              ● {entry.confidence} confidence
            </span>
          )}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px 24px' }}>
          <ScoreBar label="Fundamental" value={entry.fundamental} color="#3b82f6" />
          <ScoreBar label="Technical"   value={entry.technical}   color="#8b5cf6" />
          <ScoreBar
            label="Composite"
            value={entry.score}
            color={scoreColor(entry.score)}
          />
        </div>

        {/* Extra metrics row */}
        <div style={{ display: 'flex', gap: '16px', marginTop: '8px', flexWrap: 'wrap' }}>
          {entry.capm != null && (
            <span style={{ fontSize: '11px', color: 'var(--color-text-secondary)' }}>
              CAPM: <span style={{ color: 'var(--color-text-primary)', fontFamily: 'var(--font-mono)' }}>
                {(entry.capm * 100).toFixed(1)}%
              </span>
            </span>
          )}
          {entry.upside_pct != null && (
            <span style={{ fontSize: '11px', color: 'var(--color-text-secondary)' }}>
              Gordon upside: <span style={{
                fontFamily: 'var(--font-mono)',
                color: entry.upside_pct >= 0 ? '#00d97e' : '#ff4757',
              }}>
                {entry.upside_pct > 0 ? '+' : ''}{entry.upside_pct.toFixed(1)}%
              </span>
            </span>
          )}
        </div>
      </div>

      {/* Right — actions */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', flexShrink: 0 }}>
        <button
          onClick={() => onReAnalyse(entry.ticker)}
          style={{
            padding: '6px 14px',
            fontSize: '12px',
            background: 'var(--color-background-secondary)',
            border: '0.5px solid var(--color-border-secondary)',
            borderRadius: 'var(--border-radius-md)',
            color: 'var(--color-text-primary)',
            cursor: 'pointer',
            whiteSpace: 'nowrap',
          }}
        >
          Re-analyse ↗
        </button>
        <button
          onClick={() => onRemove(entry.id)}
          aria-label={`Remove ${entry.ticker} from history`}
          style={{
            padding: '6px 14px',
            fontSize: '12px',
            background: 'transparent',
            border: '0.5px solid var(--color-border-tertiary)',
            borderRadius: 'var(--border-radius-md)',
            color: 'var(--color-text-secondary)',
            cursor: 'pointer',
          }}
        >
          Remove
        </button>
      </div>
    </div>
  )
}

export default function History({ history, onReAnalyse }) {
  const { entries, remove, clear } = history

  return (
    <div style={{ paddingTop: '1rem' }}>

      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: '4px' }}>
        <h1 style={{ fontSize: '22px', fontWeight: 500, color: 'var(--color-text-primary)' }}>
          History
        </h1>
        {entries.length > 0 && (
          <button
            onClick={clear}
            style={{
              fontSize: '11px',
              background: 'transparent',
              border: 'none',
              color: 'var(--color-text-secondary)',
              cursor: 'pointer',
              padding: '4px 0',
            }}
          >
            Clear all
          </button>
        )}
      </div>

      <p style={{ fontSize: '13px', color: 'var(--color-text-secondary)', marginBottom: '20px' }}>
        {entries.length > 0
          ? `${entries.length} analysis${entries.length !== 1 ? 'es' : ''} saved · newest first`
          : 'No analyses yet — run an analysis to start tracking history.'}
      </p>

      {entries.length === 0 ? (
        <EmptyState message="Run an analysis using the ticker input in the sidebar. Results will appear here automatically." />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {entries.map(entry => (
            <HistoryRow
              key={entry.id}
              entry={entry}
              onReAnalyse={onReAnalyse}
              onRemove={remove}
            />
          ))}
        </div>
      )}

      {entries.length > 0 && (
        <p style={{ fontSize: '10px', color: 'var(--color-text-secondary)', marginTop: '16px', textAlign: 'center' }}>
          Stored in your browser · max {20} entries · clears when you clear browser data
        </p>
      )}
    </div>
  )
}
