import { useTranslation } from 'react-i18next'

/* ── helpers ─────────────────────────────────────────────────────────────── */

export function signalClass(signal) {
  if (!signal) return 'text-slate-400'
  const s = signal.toLowerCase()
  if (s === 'buy')     return 'signal-buy'
  if (s === 'sell')    return 'signal-sell'
  return 'signal-neutral'
}

export function badgeClass(signal) {
  if (!signal) return 'bg-slate-800 text-slate-400 border border-slate-700'
  const s = signal.toLowerCase()
  if (s === 'buy')     return 'badge-buy'
  if (s === 'sell')    return 'badge-sell'
  return 'badge-neutral'
}

export function scoreColor(score) {
  if (score >= 60) return '#00d97e'
  if (score < 40)  return '#ff4757'
  return '#f5a623'
}

/* ── SignalBadge ─────────────────────────────────────────────────────────── */

export function SignalBadge({ signal, score }) {
  const { t } = useTranslation()
  const key = `signal_${signal?.toLowerCase()}`
  const label = t(key, signal?.toUpperCase())

  return (
    <div className={`inline-flex items-center gap-2.5 px-4 py-2 rounded-lg text-sm font-mono font-semibold tracking-widest ${badgeClass(signal)}`}>
      <span
        className={`signal-dot w-2 h-2 rounded-full ${signalClass(signal)}`}
        style={{ backgroundColor: 'currentColor' }}
      />
      {label}
      {score !== undefined && (
        <span className="opacity-60 text-xs font-normal ml-1">{score.toFixed(0)}/100</span>
      )}
    </div>
  )
}

/* ── ScoreBar ────────────────────────────────────────────────────────────── */

export function ScoreBar({ label, value, color, delay = 0 }) {
  return (
    <div className="mb-3">
      <div className="flex justify-between items-center mb-1.5">
        <span className="text-xs text-slate-400 font-body">{label}</span>
        <span
          className="text-xs font-mono font-semibold"
          style={{ color }}
        >
          {value?.toFixed(0)}
        </span>
      </div>
      <div className="score-bar-track">
        <div
          className="score-bar-fill"
          style={{
            width: `${Math.min(value ?? 0, 100)}%`,
            backgroundColor: color,
            animationDelay: `${delay}ms`,
          }}
        />
      </div>
    </div>
  )
}

/* ── MetricCard ──────────────────────────────────────────────────────────── */

export function MetricCard({ label, value, delta, deltaPositive, help }) {
  const deltaColor = deltaPositive === true
    ? '#00d97e'
    : deltaPositive === false
      ? '#ff4757'
      : '#f5a623'

  return (
    <div className="metric-card">
      <div className="text-[11px] text-slate-500 uppercase tracking-widest mb-1.5 font-body">
        {label}
      </div>
      <div className="text-xl font-mono font-semibold text-slate-100 leading-tight">
        {value ?? '—'}
      </div>
      {delta && (
        <div className="text-xs font-mono mt-1" style={{ color: deltaColor }}>
          {delta}
        </div>
      )}
      {help && (
        <div className="text-[11px] text-slate-600 mt-1.5 font-body leading-relaxed">
          {help}
        </div>
      )}
    </div>
  )
}

/* ── SignalRow ────────────────────────────────────────────────────────────── */

export function SignalRow({ label, signal, valueStr, note }) {
  const { t } = useTranslation()
  const sigKey = `signal_${signal?.toLowerCase()}`
  const sigLabel = t(sigKey, signal?.toUpperCase() ?? '—')

  return (
    <div className="flex items-start justify-between py-2.5 border-b border-bg-border last:border-0">
      <span className="text-sm text-slate-300 font-body">{label}</span>
      <div className="text-right ml-4">
        <div className="flex items-center gap-2 justify-end">
          <span className="text-xs font-mono text-slate-400">{valueStr}</span>
          <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full tracking-wide ${badgeClass(signal)}`}>
            {sigLabel}
          </span>
        </div>
        {note && (
          <div className="text-[10px] text-slate-600 mt-0.5 font-body">{note}</div>
        )}
      </div>
    </div>
  )
}

/* ── ExplainBox ──────────────────────────────────────────────────────────── */

export function ExplainBox({ title, children, source }) {
  return (
    <div className="mt-3 rounded-lg border-l-2 border-accent bg-accent/5 border border-accent/10 p-3.5">
      <div className="text-xs font-semibold text-blue-300 mb-2 font-body">{title}</div>
      <div className="text-xs text-slate-400 leading-relaxed font-body">{children}</div>
      {source && (
        <div className="text-[10px] text-slate-600 mt-2 italic font-body">
          📚 {source}
        </div>
      )}
    </div>
  )
}

/* ── DataWarnings ─────────────────────────────────────────────────────────── */

export function DataWarnings({ warnings }) {
  const { t } = useTranslation()
  if (!warnings?.length) return null

  return (
    <details className="mt-3">
      <summary className="text-xs text-signal-neutral cursor-pointer font-body select-none">
        ⚠ {t('section_warnings')} ({warnings.length})
      </summary>
      <div className="mt-2 space-y-1">
        {warnings.map((w, i) => (
          <div key={i} className="text-[11px] text-slate-500 font-body leading-relaxed pl-2 border-l border-signal-neutral/30">
            {w}
          </div>
        ))}
      </div>
    </details>
  )
}

/* ── SectionHeader ────────────────────────────────────────────────────────── */

export function SectionHeader({ title, subtitle }) {
  return (
    <div className="mb-4">
      <h2 className="text-base font-display font-semibold text-slate-100">{title}</h2>
      {subtitle && (
        <p className="text-xs text-slate-500 mt-0.5 font-body">{subtitle}</p>
      )}
    </div>
  )
}

/* ── Spinner ─────────────────────────────────────────────────────────────── */

export function Spinner() {
  return (
    <div className="flex items-center justify-center py-16">
      <div className="w-6 h-6 rounded-full border-2 border-accent border-t-transparent animate-spin" />
    </div>
  )
}

/* ── EmptyState ──────────────────────────────────────────────────────────── */

export function EmptyState({ message }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="text-4xl mb-4">📈</div>
      <p className="text-sm text-slate-500 font-body max-w-xs">{message}</p>
    </div>
  )
}

/* ── ErrorState ──────────────────────────────────────────────────────────── */

export function ErrorState({ error }) {
  const { t } = useTranslation()
  const msg = error?.status === 404
    ? t('error_not_found')
    : t('error_generic')

  return (
    <div className="mx-auto max-w-md mt-8 p-4 rounded-lg bg-signal-sell/10 border border-signal-sell/20">
      <p className="text-sm text-signal-sell font-body">{msg}</p>
      {error?.message && (
        <p className="text-xs text-slate-500 mt-1 font-mono">{error.message}</p>
      )}
    </div>
  )
}
