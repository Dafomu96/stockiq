import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { analyzePortfolio } from '../lib/api'
import { MetricCard, ExplainBox, SectionHeader, Spinner } from '../components/ui'
import { AllocationBars, DriftChart } from '../components/Charts'

const ASSET_CLASSES = [
  { key: 'domestic_equity',      label: 'Domestic equity (US)',     default: 30 },
  { key: 'international_equity', label: 'International equity',      default: 15 },
  { key: 'emerging_markets',     label: 'Emerging markets',          default: 5  },
  { key: 'real_estate',          label: 'Real estate (REITs)',        default: 20 },
  { key: 'government_bonds',     label: 'Government bonds',          default: 15 },
  { key: 'inflation_protected',  label: 'Inflation-protected (TIPS)', default: 15 },
]

export default function Portfolio() {
  const { t } = useTranslation()

  const [totalValue, setTotalValue] = useState(10000)
  const [alloc, setAlloc] = useState(
    Object.fromEntries(ASSET_CLASSES.map(a => [a.key, a.default]))
  )
  const [result,  setResult]  = useState(null)
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState(null)

  async function run() {
    setLoading(true)
    setError(null)
    try {
      const allocation = Object.fromEntries(
        Object.entries(alloc).map(([k, v]) => [k, v / 100])
      )
      const data = await analyzePortfolio(allocation, totalValue, 10)
      setResult(data)
    } catch (err) {
      setError(err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page-enter space-y-6">

      <h1 className="text-2xl font-display font-bold text-slate-100">{t('portfolio_title')}</h1>

      {/* ── Inputs ── */}
      <div className="card space-y-4">
        <div>
          <label className="text-xs text-slate-400 font-body block mb-1.5">
            {t('portfolio_title')} value (€)
          </label>
          <input
            type="number" value={totalValue}
            onChange={e => setTotalValue(Number(e.target.value))}
            className="w-full sm:w-48 bg-bg-secondary border border-bg-border rounded-lg px-3 py-2 text-sm font-mono text-slate-200 focus:outline-none focus:border-accent"
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {ASSET_CLASSES.map(ac => (
            <div key={ac.key}>
              <div className="flex justify-between mb-1">
                <label className="text-xs text-slate-400 font-body">{ac.label}</label>
                <span className="text-xs font-mono text-accent">{alloc[ac.key]}%</span>
              </div>
              <input
                type="range" min="0" max="100" step="1"
                value={alloc[ac.key]}
                onChange={e => setAlloc(prev => ({ ...prev, [ac.key]: Number(e.target.value) }))}
                className="w-full accent-accent"
              />
            </div>
          ))}
        </div>

        <button onClick={run} disabled={loading} className="btn-primary">
          {loading ? t('analyzing') : 'Analyse portfolio'}
        </button>

        <ExplainBox title="Swensen model portfolio" source="Swensen (2005) Unconventional Success, Ch.8">
          David Swensen (Yale CIO) demonstrated that low-cost diversification across 6
          uncorrelated asset classes, rebalanced when drift exceeds 5pp, delivers
          superior long-term risk-adjusted returns for individual investors.
        </ExplainBox>
      </div>

      {loading && <Spinner />}

      {result && !loading && (
        <>
          {/* ── Summary metrics ── */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 stagger">
            <MetricCard
              label={t('portfolio_score')}
              value={`${result.swensen_score.toFixed(0)}/100`}
              deltaPositive={result.swensen_score >= 75}
            />
            <MetricCard
              label="Status"
              value={result.needs_rebalancing ? t('portfolio_rebalance') : t('portfolio_ok')}
            />
            <MetricCard
              label={t('portfolio_cost')}
              value={`€${result.annual_cost_estimate.toFixed(2)}/yr`}
            />
            <MetricCard
              label="Actions needed"
              value={String(result.rebalancing_actions.length)}
            />
          </div>

          {/* ── Allocation bars + drift ── */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="card">
              <SectionHeader title="Current vs target allocation" />
              <AllocationBars positions={result.positions} />
            </div>
            <div className="card">
              <SectionHeader title="Drift from target (pp)" subtitle="Amber lines = 5pp threshold" />
              <DriftChart positions={result.positions} />
            </div>
          </div>

          {/* ── Rebalancing actions ── */}
          {result.rebalancing_actions.length > 0 && (
            <div className="card">
              <SectionHeader title="Rebalancing actions required" />
              <div className="space-y-3">
                {result.rebalancing_actions.map((action, i) => {
                  const color = action.action === 'sell' ? '#ff4757' : '#00d97e'
                  const label = action.asset_class.replace(/_/g, ' ')
                    .replace(/\b\w/g, c => c.toUpperCase())
                  return (
                    <div key={i} className="flex items-center justify-between py-3 border-b border-bg-border last:border-0">
                      <div>
                        <span className="text-sm font-body text-slate-200">{label}</span>
                        <span className="ml-2 text-xs font-mono text-slate-500">{action.etf_ticker}</span>
                      </div>
                      <div className="text-right">
                        <span
                          className="text-xs font-semibold font-mono px-2 py-0.5 rounded-full"
                          style={{ background: `${color}18`, color }}
                        >
                          {action.action.toUpperCase()}
                        </span>
                        <div className="text-sm font-mono font-semibold text-slate-200 mt-1">
                          €{action.amount.toLocaleString('es-ES', { maximumFractionDigits: 0 })}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
              <p className="text-[10px] text-slate-600 font-body mt-3">
                Swensen (2005) p.195: "Rebalance when positions drift more than 5pp from targets."
              </p>
            </div>
          )}

          {/* ── Notes ── */}
          <details className="card">
            <summary className="text-xs text-slate-500 cursor-pointer font-body">📝 Analysis notes</summary>
            <ul className="mt-3 space-y-1.5">
              {result.notes.map((n, i) => (
                <li key={i} className="text-xs text-slate-400 font-body leading-relaxed">{n}</li>
              ))}
            </ul>
          </details>

          <p className="text-[10px] text-slate-600 font-body text-center">{result.disclaimer}</p>
        </>
      )}

      {error && (
        <p className="text-sm text-signal-sell font-body">{error.message}</p>
      )}
    </div>
  )
}
