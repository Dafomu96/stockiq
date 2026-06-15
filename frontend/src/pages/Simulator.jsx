import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { simulate } from '../lib/api'
import { MetricCard, ExplainBox, SectionHeader, Spinner } from '../components/ui'
import { SimulationChart } from '../components/Charts'

export default function Simulator({ analysisResult }) {
  const { t } = useTranslation()

  const [investment, setInvestment] = useState(10000)
  const [horizon,    setHorizon]    = useState(10)
  const [monthly,    setMonthly]    = useState(0)
  const [result,     setResult]     = useState(null)
  const [loading,    setLoading]    = useState(false)
  const [error,      setError]      = useState(null)

  const ticker = analysisResult?.ticker ?? 'AAPL'
  const capmReturn = analysisResult?.fundamental?.capm?.required_return ?? null
  const gordonFV   = analysisResult?.fundamental?.gordon?.fair_value ?? null
  const currPrice  = analysisResult?.fundamental?.gordon?.current_price ?? null

  async function run() {
    setLoading(true)
    setError(null)
    try {
      const data = await simulate({
        ticker,
        initial_investment: investment,
        horizon_years: horizon,
        monthly_contribution: monthly,
        capm_required_return: capmReturn,
        gordon_fair_value: gordonFV,
        current_price: currPrice,
      })
      setResult(data)
    } catch (err) {
      setError(err)
    } finally {
      setLoading(false)
    }
  }

  const pess = result?.scenarios?.[0]
  const base = result?.scenarios?.[1]
  const opt  = result?.scenarios?.[2]
  const risk = result?.risk
  const be   = result?.break_even

  return (
    <div className="page-enter space-y-6">

      <div>
        <h1 className="text-2xl font-display font-bold text-slate-100">{t('sim_title')}</h1>
        <p className="text-xs text-slate-500 mt-0.5 font-body">{ticker}</p>
      </div>

      {/* ── Inputs ── */}
      <div className="card">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
          <div>
            <label className="text-xs text-slate-400 font-body block mb-1.5">{t('sim_investment')} (€)</label>
            <input
              type="number" value={investment}
              onChange={e => setInvestment(Number(e.target.value))}
              className="w-full bg-bg-secondary border border-bg-border rounded-lg px-3 py-2 text-sm font-mono text-slate-200 focus:outline-none focus:border-accent"
            />
          </div>
          <div>
            <label className="text-xs text-slate-400 font-body block mb-1.5">{t('sim_horizon')}</label>
            <input
              type="range" min="1" max="30" value={horizon}
              onChange={e => setHorizon(Number(e.target.value))}
              className="w-full accent-accent"
            />
            <div className="text-xs font-mono text-accent text-center mt-1">{horizon} years</div>
          </div>
          <div>
            <label className="text-xs text-slate-400 font-body block mb-1.5">{t('sim_monthly')} (€/mo)</label>
            <input
              type="number" value={monthly} min="0"
              onChange={e => setMonthly(Number(e.target.value))}
              className="w-full bg-bg-secondary border border-bg-border rounded-lg px-3 py-2 text-sm font-mono text-slate-200 focus:outline-none focus:border-accent"
            />
          </div>
        </div>

        {capmReturn && (
          <p className="text-xs text-slate-500 font-body mt-3">
            Base rate from CAPM: <span className="text-accent font-mono">{(capmReturn * 100).toFixed(1)}%</span>
          </p>
        )}

        <button
          onClick={run} disabled={loading}
          className="btn-primary mt-4 w-full sm:w-auto"
        >
          {loading ? t('analyzing') : t('sim_run')}
        </button>
      </div>

      {loading && <Spinner />}

      {result && !loading && (
        <>
          {/* ── Scenario cards ── */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 stagger">
            <MetricCard
              label={`📉 ${t('sim_pessimistic')} (${(pess.annual_rate * 100).toFixed(0)}%/yr)`}
              value={`€${pess.final_value.toLocaleString('es-ES', { maximumFractionDigits: 0 })}`}
              delta={`+${pess.gain_pct.toFixed(1)}%`}
              deltaPositive={true}
            />
            <MetricCard
              label={`📊 ${t('sim_base')} (${(base.annual_rate * 100).toFixed(1)}%/yr)`}
              value={`€${base.final_value.toLocaleString('es-ES', { maximumFractionDigits: 0 })}`}
              delta={`+${base.gain_pct.toFixed(1)}%`}
              deltaPositive={true}
            />
            <MetricCard
              label={`📈 ${t('sim_optimistic')} (${(opt.annual_rate * 100).toFixed(0)}%/yr)`}
              value={`€${opt.final_value.toLocaleString('es-ES', { maximumFractionDigits: 0 })}`}
              delta={`+${opt.gain_pct.toFixed(1)}%`}
              deltaPositive={true}
            />
          </div>

          {/* ── Chart ── */}
          <div className="card">
            <SectionHeader title="Portfolio projection" />
            <SimulationChart
              yearByYear={result.year_by_year}
              initialInvestment={investment}
              hasDCA={monthly > 0}
            />
          </div>

          {/* ── Risk + break-even ── */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="card">
              <SectionHeader title="Risk metrics" />
              <div className="grid grid-cols-2 gap-3 stagger">
                <MetricCard label={t('sim_sharpe')} value={risk.sharpe_ratio.toFixed(2)} help="> 1.0 = good risk/return" />
                <MetricCard label={t('sim_var')}    value={`${(risk.value_at_risk_95 * 100).toFixed(1)}%`} help="Parametric 95% confidence" />
                <MetricCard label={t('sim_drawdown')} value={`${(risk.max_drawdown_estimate * 100).toFixed(1)}%`} help="Estimated peak-to-trough" />
                <MetricCard label="Break-even" value={risk.break_even_years > 0 ? `${risk.break_even_years.toFixed(1)} yrs` : '< 1yr'} />
              </div>
              <ExplainBox title="Sharpe & VaR" source="Bodie, Kane, Marcus (2014) Ch.5; Sharpe (1994)">
                Sharpe = (r − rf) / σ = {risk.sharpe_ratio.toFixed(2)}.
                VaR(95%) = {(risk.value_at_risk_95 * 100).toFixed(1)}% max expected 1-year loss.
                Volatility source: {risk.volatility_source}.
              </ExplainBox>
            </div>

            <div className="card">
              <SectionHeader title="Margin of safety" />
              {be.margin_of_safety != null ? (
                <>
                  <div className="flex items-center gap-3 mb-3">
                    <div className="text-2xl font-mono font-bold"
                      style={{ color: be.margin_of_safety > 0 ? '#00d97e' : '#ff4757' }}>
                      {be.margin_of_safety > 0 ? '+' : ''}{(be.margin_of_safety * 100).toFixed(1)}%
                    </div>
                    <div className="text-sm font-body text-slate-400">
                      {be.is_undervalued ? 'discount to intrinsic value' : 'premium over intrinsic value'}
                    </div>
                  </div>
                  <div className="text-xs text-slate-500 font-body">
                    Current: {be.current_price?.toFixed(2)} · Gordon fair value: {be.gordon_fair_value?.toFixed(2)}
                  </div>
                  <ExplainBox title="Margin of safety" source="Graham (1949); Shiller (2000)">
                    Buy at a discount to intrinsic value to protect against valuation errors.
                    {be.margin_of_safety > 0
                      ? ' Positive margin provides a buffer against optimistic growth assumptions.'
                      : ' Negative margin means you are paying above intrinsic value.'}
                  </ExplainBox>
                </>
              ) : (
                <p className="text-sm text-slate-500 font-body">
                  No Gordon fair value available (no dividend). Run /v1/analyze first.
                </p>
              )}
            </div>
          </div>

          {/* ── Assumptions ── */}
          <details className="card">
            <summary className="text-xs text-slate-500 cursor-pointer font-body select-none">
              🔍 Assumptions used
            </summary>
            <div className="mt-3 grid grid-cols-2 gap-1">
              {Object.entries(result.assumptions).map(([k, v]) => (
                <div key={k} className="text-[11px] font-body">
                  <span className="text-slate-600">{k.replace(/_/g, ' ')}: </span>
                  <span className="font-mono text-slate-400">{v}</span>
                </div>
              ))}
            </div>
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
