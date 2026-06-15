import { useTranslation } from 'react-i18next'
import {
  SignalBadge, ScoreBar, MetricCard, DataWarnings,
  SectionHeader, EmptyState, ErrorState, Spinner, scoreColor,
} from '../components/ui'

export default function Overview({ result, loading, error }) {
  const { t } = useTranslation()

  if (loading) return <Spinner />
  if (error)   return <ErrorState error={error} />
  if (!result) return <EmptyState message={t('no_ticker')} />

  const { ticker, composite_score, signal, score_breakdown, confidence,
          confidence_reasons, fundamental, technical, summary_notes, analysed_at } = result

  const fund = fundamental
  const capm = fund.capm
  const gordon = fund.gordon
  const pe = fund.pe

  // Price delta
  const price = fund?.capm ? null : null // from info — not in CompositeResult
  const gordonFV = gordon?.fair_value
  const upside = gordon?.upside_pct

  const confColor = { high: '#00d97e', medium: '#f5a623', low: '#ff4757' }[confidence] ?? '#4a5568'
  const confLabel = { high: 'High', medium: 'Medium', low: 'Low' }[confidence] ?? confidence

  return (
    <div className="page-enter space-y-6">

      {/* ── Header ── */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-baseline gap-3">
            <h1 className="text-3xl font-display font-bold text-slate-100 tracking-tight">
              {ticker}
            </h1>
            <span className="text-sm text-slate-500 font-body">
              {t('analysed_at')} {analysed_at?.slice(0, 10)}
            </span>
          </div>
          <div className="flex items-center gap-3 mt-2">
            <SignalBadge signal={signal} score={composite_score} />
            <span className="text-xs font-body" style={{ color: confColor }}>
              ● {t('confidence')}: {confLabel}
            </span>
          </div>
        </div>
      </div>

      {/* ── Score gauges ── */}
      <div className="card">
        <ScoreBar
          label={t('fundamental_score')}
          value={score_breakdown?.fundamental}
          color="#3b82f6"
          delay={0}
        />
        <ScoreBar
          label={t('technical_score')}
          value={score_breakdown?.technical}
          color="#8b5cf6"
          delay={60}
        />
        <ScoreBar
          label={t('composite_score')}
          value={composite_score}
          color={scoreColor(composite_score)}
          delay={120}
        />
      </div>

      {/* ── Key metrics ── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 stagger">
        <MetricCard
          label={t('metric_capm')}
          value={capm ? `${(capm.required_return * 100).toFixed(1)}%` : '—'}
          help="r = rf + β·(rm − rf)"
        />
        <MetricCard
          label={t('metric_fair_value')}
          value={gordonFV ? `${gordonFV.toFixed(2)}` : '—'}
          delta={upside != null ? `${upside > 0 ? '+' : ''}${upside.toFixed(1)}% upside` : null}
          deltaPositive={upside != null ? upside > 0 : null}
          help="Gordon Growth Model"
        />
        <MetricCard
          label={t('metric_beta')}
          value={capm?.beta?.toFixed(2) ?? '—'}
          delta={capm?.beta > 1 ? 'More volatile than market' : capm?.beta < 1 ? 'Less volatile' : null}
        />
        <MetricCard
          label={t('metric_pe')}
          value={pe?.actual_pe?.toFixed(1) ?? '—'}
          delta={pe?.theoretical_pe ? `Theoretical: ${pe.theoretical_pe.toFixed(1)}` : null}
          help={pe?.interpretation?.replace(/_/g, ' ')}
        />
      </div>

      {/* ── Summary notes ── */}
      {summary_notes?.length > 0 && (
        <div className="card">
          <SectionHeader title={t('section_means')} />
          <div className="space-y-2">
            {summary_notes.map((note, i) => {
              if (note.startsWith('──')) {
                return (
                  <div key={i} className="text-[10px] text-accent uppercase tracking-widest font-semibold mt-3 mb-1 font-body">
                    {note.replace(/──/g, '').trim()}
                  </div>
                )
              }
              return (
                <p key={i} className="text-xs text-slate-400 leading-relaxed font-body pl-3 border-l border-bg-border">
                  {note}
                </p>
              )
            })}
          </div>
        </div>
      )}

      {/* ── Warnings ── */}
      <DataWarnings warnings={[...( confidence_reasons ?? []), ...(technical?.data_quality_warnings ?? [])]} />
    </div>
  )
}
