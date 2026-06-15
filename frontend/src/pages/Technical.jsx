import { useTranslation } from 'react-i18next'
import {
  SignalBadge, SignalRow, ExplainBox, DataWarnings,
  SectionHeader, EmptyState, Spinner, ErrorState,
} from '../components/ui'

export default function Technical({ result, loading, error }) {
  const { t } = useTranslation()

  if (loading) return <Spinner />
  if (error)   return <ErrorState error={error} />
  if (!result) return <EmptyState message={t('no_ticker')} />

  const tech = result.technical

  const rsi  = tech.rsi
  const macd = tech.macd
  const bb   = tech.bollinger
  const ma   = tech.moving_averages
  const obv  = tech.obv
  const adx  = tech.adx

  const rsiZone = rsi.signal === 'buy'
    ? 'Oversold — potential reversal up'
    : rsi.signal === 'sell'
      ? 'Overbought — potential reversal down'
      : 'Neutral zone'

  const crossover = macd.is_bullish_crossover
    ? 'Bullish crossover'
    : macd.is_bearish_crossover
      ? 'Bearish crossover'
      : macd.histogram != null
        ? macd.histogram > 0 ? 'Positive histogram' : 'Negative histogram'
        : 'N/A'

  const bbZone = bb.signal === 'buy'
    ? 'Near lower band'
    : bb.signal === 'sell'
      ? 'Near upper band'
      : 'Inside bands'

  const maCross = ma.golden_cross
    ? 'Golden Cross (SMA50 > SMA200)'
    : ma.death_cross
      ? 'Death Cross (SMA50 < SMA200)'
      : 'No crossover'

  return (
    <div className="page-enter space-y-6">

      {/* ── Header ── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-display font-bold text-slate-100">
            {t('nav_technical')}
          </h1>
          <p className="text-xs text-slate-500 mt-0.5 font-body">
            {result.ticker} · Score: {tech.score.toFixed(0)}/100
          </p>
        </div>
        <SignalBadge signal={tech.signal} score={tech.score} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* ── Signal table ── */}
        <div className="card">
          <SectionHeader title={t('section_signals')} />

          <SignalRow
            label="RSI (14)"
            signal={rsi.signal}
            valueStr={rsi.value != null ? `${rsi.value.toFixed(1)} — ${rsiZone}` : 'N/A'}
          />
          <SignalRow
            label="MACD"
            signal={macd.signal}
            valueStr={crossover}
            note={macd.histogram != null ? `Histogram: ${macd.histogram.toFixed(4)}` : undefined}
          />
          <SignalRow
            label="Bollinger Bands"
            signal={bb.signal}
            valueStr={bb.percent_b != null ? `%B = ${bb.percent_b.toFixed(2)} — ${bbZone}` : 'N/A'}
          />
          <SignalRow
            label="Moving Averages"
            signal={ma.signal}
            valueStr={maCross}
            note={ma.sma_200 ? `SMA200: ${ma.sma_200.toFixed(2)}` : 'SMA200 not available'}
          />
          <SignalRow
            label="OBV"
            signal={obv.signal}
            valueStr={`Volume ${obv.volume_trend} — ${obv.confirms_price_trend ? 'confirms trend' : 'diverges'}`}
          />
          <SignalRow
            label="ADX"
            signal={adx.signal}
            valueStr={adx.adx != null ? `${adx.adx.toFixed(1)} — ${adx.trend_strength}` : 'N/A'}
            note={adx.plus_di && adx.minus_di ? `+DI: ${adx.plus_di.toFixed(1)} / −DI: ${adx.minus_di.toFixed(1)}` : undefined}
          />
        </div>

        {/* ── Explanations ── */}
        <div className="space-y-0">
          <SectionHeader title={t('section_means')} />

          <ExplainBox
            title="RSI — Relative Strength Index"
            source="Murphy (1999) Technical Analysis, p.225"
          >
            Oscillator 0–100 measuring momentum. Below {rsi.oversold_threshold} = oversold (potential buy).
            Above {rsi.overbought_threshold} = overbought (potential sell). Current value: {rsi.value?.toFixed(1) ?? 'N/A'}.
          </ExplainBox>

          <ExplainBox
            title="MACD — Convergence/Divergence"
            source="Murphy (1999) Technical Analysis, p.233"
          >
            MACD = EMA(12) − EMA(26). A bullish crossover (MACD crosses above signal line)
            signals rising momentum. Current histogram: {macd.histogram?.toFixed(4) ?? 'N/A'}.
          </ExplainBox>

          <ExplainBox
            title={ma.golden_cross ? 'Golden Cross active 🟢' : ma.death_cross ? 'Death Cross active 🔴' : 'Moving averages'}
            source="Murphy (1999) Technical Analysis, p.193–196"
          >
            The 200-day SMA is the most widely watched long-term trend indicator.
            {ma.golden_cross && ' Golden Cross (SMA50 > SMA200) = long-term bullish signal.'}
            {ma.death_cross  && ' Death Cross (SMA50 < SMA200) = long-term bearish signal.'}
            {!ma.sma_200     && ' SMA200 not available — insufficient price history.'}
          </ExplainBox>

          <ExplainBox
            title="ADX — Trend Strength"
            source="Murphy (1999) Technical Analysis, p.344"
          >
            ADX &gt; 25 = strong trend in force. Current: {adx.adx?.toFixed(1) ?? 'N/A'} ({adx.trend_strength}).
            ADX does not indicate direction — only strength.
          </ExplainBox>
        </div>
      </div>

      <DataWarnings warnings={tech.data_quality_warnings} />
    </div>
  )
}
