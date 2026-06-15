import { useTranslation } from 'react-i18next'
import {
  SignalBadge, MetricCard, ExplainBox, ScoreBar,
  SectionHeader, EmptyState, Spinner, ErrorState,
} from '../components/ui'

export default function Fundamental({ result, loading, error }) {
  const { t } = useTranslation()

  if (loading) return <Spinner />
  if (error)   return <ErrorState error={error} />
  if (!result) return <EmptyState message={t('no_ticker')} />

  const fund = result.fundamental
  const { capm, gordon, pe } = fund

  const interpColors = {
    undervalued: '#00d97e',
    fairly_valued: '#f5a623',
    overvalued: '#ff4757',
    insufficient_data: '#4a5568',
  }

  return (
    <div className="page-enter space-y-6">

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-display font-bold text-slate-100">
            {t('nav_fundamental')}
          </h1>
          <p className="text-xs text-slate-500 mt-0.5 font-body">
            {result.ticker} · Score: {fund.score.toFixed(0)}/100
          </p>
        </div>
        <SignalBadge signal={fund.signal} score={fund.score} />
      </div>

      {/* ── CAPM ── */}
      <div className="card">
        <SectionHeader title="CAPM — Required Return" />
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4 stagger">
          <MetricCard label="Required return" value={`${(capm.required_return * 100).toFixed(2)}%`} help="r = rf + β·(rm − rf)" />
          <MetricCard label="Beta (β)"         value={capm.beta.toFixed(3)} />
          <MetricCard label="Risk-free rate"   value={`${(capm.risk_free_rate * 100).toFixed(2)}%`} />
          <MetricCard label="Market premium"   value={`${(capm.market_risk_premium * 100).toFixed(2)}%`} />
        </div>
        <ExplainBox title="What does the CAPM return mean?" source="Bodie, Kane, Marcus (2014) Investments, Ch.9">
          The CAPM return ({(capm.required_return * 100).toFixed(1)}%) is the minimum annual return the market
          demands for this asset's level of systematic risk (β = {capm.beta.toFixed(2)}).
          This value becomes the discount rate r in the Gordon model.
        </ExplainBox>
      </div>

      {/* ── Gordon Growth Model ── */}
      <div className="card">
        <SectionHeader title="Gordon Growth Model" />
        {gordon?.fair_value != null ? (
          <>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-4 stagger">
              <MetricCard
                label="Fair value"
                value={gordon.fair_value.toFixed(2)}
                delta={gordon.upside_pct != null ? `${gordon.upside_pct > 0 ? '+' : ''}${gordon.upside_pct.toFixed(1)}% upside` : null}
                deltaPositive={gordon.upside_pct > 0}
              />
              <MetricCard label="Dividend (D)" value={gordon.dividend.toFixed(4)} />
              <MetricCard label="Growth rate (g)" value={`${(gordon.growth_rate * 100).toFixed(1)}%`} />
            </div>
            {gordon.assumption_warning && (
              <p className="text-xs text-signal-neutral font-body bg-signal-neutral/10 rounded p-2">
                ⚠ {gordon.assumption_warning}
              </p>
            )}
            <ExplainBox title="P = D / (r − g)" source="Gordon (1962); Shiller (2000) Irrational Exuberance">
              Fair value = {gordon.dividend.toFixed(4)} / ({(gordon.discount_rate * 100).toFixed(1)}% − {(gordon.growth_rate * 100).toFixed(1)}%) = {gordon.fair_value.toFixed(2)}.
              {gordon.upside_pct > 0
                ? ` The stock appears ${gordon.upside_pct.toFixed(1)}% undervalued vs intrinsic value.`
                : ` The stock appears ${Math.abs(gordon.upside_pct ?? 0).toFixed(1)}% overvalued vs intrinsic value.`
              }
            </ExplainBox>
          </>
        ) : (
          <p className="text-sm text-slate-500 font-body">
            {gordon?.assumption_warning ?? 'Gordon model not applicable — no dividend data available.'}
          </p>
        )}
      </div>

      {/* ── P/E ── */}
      <div className="card">
        <SectionHeader title="P/E Ratio Analysis" />
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-4">
          <MetricCard label="Actual P/E (TTM)" value={pe.actual_pe?.toFixed(1) ?? 'N/A'} />
          <MetricCard label="Theoretical P/E"  value={pe.theoretical_pe?.toFixed(1) ?? 'N/A'} help="1/(r−g)" />
          <MetricCard label="Forward P/E"      value={pe.forward_pe?.toFixed(1) ?? 'N/A'} />
        </div>
        <div className="flex items-center gap-2 mb-3">
          <span className="text-sm text-slate-400 font-body">Interpretation:</span>
          <span className="text-sm font-semibold font-body" style={{ color: interpColors[pe.interpretation] }}>
            {pe.interpretation.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
          </span>
          {pe.pe_gap != null && (
            <span className="text-xs text-slate-600 font-mono">(gap: {pe.pe_gap > 0 ? '+' : ''}{pe.pe_gap.toFixed(1)})</span>
          )}
        </div>
        <ExplainBox title="P/E = 1 / (r − g)" source="Shiller (2000) Irrational Exuberance, Ch.3">
          The theoretical P/E = 1/(r−g) = {pe.theoretical_pe?.toFixed(1) ?? 'N/A'}.
          A market P/E above this level implies investors expect higher growth than assumed,
          or the stock is overvalued.
        </ExplainBox>
      </div>

      {/* ── Score breakdown ── */}
      <div className="card">
        <SectionHeader title="Score breakdown" />
        {Object.entries(fund.components).map(([key, val]) => (
          <ScoreBar key={key} label={key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())} value={val} color={val >= 60 ? '#00d97e' : val < 40 ? '#ff4757' : '#f5a623'} />
        ))}
      </div>

    </div>
  )
}
