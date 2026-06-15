import {
  AreaChart, Area, LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, ReferenceLine,
} from 'recharts'

const COLORS = {
  blue: '#3b82f6',
  green: '#00d97e',
  red: '#ff4757',
  amber: '#f5a623',
  purple: '#8b5cf6',
  muted: '#4a5568',
  grid: '#1a2540',
}

const tooltipStyle = {
  backgroundColor: '#0d1628',
  border: '1px solid #1a2540',
  borderRadius: '8px',
  fontFamily: '"JetBrains Mono", monospace',
  fontSize: '11px',
  color: '#e2e8f0',
}

const fmt = (v) => {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'number') {
    if (Math.abs(v) >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`
    if (Math.abs(v) >= 1_000)    return `${(v / 1_000).toFixed(1)}k`
    return v.toFixed(2)
  }
  return v
}

/* ── SimulationChart ─────────────────────────────────────────────────────── */

export function SimulationChart({ yearByYear, initialInvestment, hasDCA }) {
  if (!yearByYear?.length) return null

  return (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart data={yearByYear} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
        <defs>
          <linearGradient id="grad-opt" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor={COLORS.green}  stopOpacity={0.15} />
            <stop offset="95%" stopColor={COLORS.green}  stopOpacity={0} />
          </linearGradient>
          <linearGradient id="grad-base" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor={COLORS.blue}   stopOpacity={0.2} />
            <stop offset="95%" stopColor={COLORS.blue}   stopOpacity={0} />
          </linearGradient>
          <linearGradient id="grad-pess" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor={COLORS.red}    stopOpacity={0.1} />
            <stop offset="95%" stopColor={COLORS.red}    stopOpacity={0} />
          </linearGradient>
        </defs>

        <CartesianGrid strokeDasharray="3 3" stroke={COLORS.grid} />

        <XAxis
          dataKey="year"
          tick={{ fill: '#4a5568', fontFamily: '"JetBrains Mono", monospace', fontSize: 10 }}
          tickLine={false}
          axisLine={{ stroke: COLORS.grid }}
          label={{ value: 'Years', position: 'insideBottom', offset: -2, fill: '#4a5568', fontSize: 10 }}
        />
        <YAxis
          tick={{ fill: '#4a5568', fontFamily: '"JetBrains Mono", monospace', fontSize: 10 }}
          tickLine={false}
          axisLine={false}
          tickFormatter={fmt}
          width={55}
        />

        <Tooltip
          contentStyle={tooltipStyle}
          formatter={(v, name) => [`€${fmt(v)}`, name]}
          labelFormatter={(l) => `Year ${l}`}
        />

        <ReferenceLine
          y={initialInvestment}
          stroke={COLORS.muted}
          strokeDasharray="4 4"
          strokeWidth={1}
        />

        <Area type="monotone" dataKey="pessimistic" name="Pessimistic (4%)"
          stroke={COLORS.red}    fill="url(#grad-pess)"
          strokeWidth={1.5} strokeDasharray="4 4" dot={false} />
        <Area type="monotone" dataKey="base"        name="Base"
          stroke={COLORS.blue}   fill="url(#grad-base)"
          strokeWidth={2.5} dot={false} />
        <Area type="monotone" dataKey="optimistic"  name="Optimistic (10%)"
          stroke={COLORS.green}  fill="url(#grad-opt)"
          strokeWidth={1.5} strokeDasharray="4 4" dot={false} />
        {hasDCA && (
          <Area type="monotone" dataKey="dca_base" name="With DCA"
            stroke={COLORS.amber} fill="none"
            strokeWidth={2} strokeDasharray="6 3" dot={false} />
        )}

        <Legend
          wrapperStyle={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 10, color: '#4a5568', paddingTop: 8 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}

/* ── DriftChart ──────────────────────────────────────────────────────────── */

export function DriftChart({ positions }) {
  if (!positions?.length) return null

  const data = positions.map(p => ({
    name: p.asset_class.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
    drift: parseFloat((p.drift_pct ?? 0).toFixed(1)),
    color: p.drift_pct > 0 ? COLORS.red : COLORS.green,
  }))

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} layout="vertical" margin={{ left: 0, right: 24, top: 4, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={COLORS.grid} horizontal={false} />
        <XAxis
          type="number"
          tick={{ fill: '#4a5568', fontSize: 10, fontFamily: '"JetBrains Mono", monospace' }}
          tickLine={false}
          axisLine={{ stroke: COLORS.grid }}
          tickFormatter={v => `${v > 0 ? '+' : ''}${v}pp`}
        />
        <YAxis
          type="category"
          dataKey="name"
          width={130}
          tick={{ fill: '#94a3b8', fontSize: 10, fontFamily: '"DM Sans", sans-serif' }}
          tickLine={false}
          axisLine={false}
        />
        <Tooltip
          contentStyle={tooltipStyle}
          formatter={v => [`${v > 0 ? '+' : ''}${v}pp`, 'Drift']}
        />
        <ReferenceLine x={5}  stroke={COLORS.amber} strokeDasharray="3 3" strokeWidth={1} />
        <ReferenceLine x={-5} stroke={COLORS.amber} strokeDasharray="3 3" strokeWidth={1} />
        <ReferenceLine x={0}  stroke={COLORS.muted} strokeWidth={1} />
        <Bar dataKey="drift" radius={[0, 4, 4, 0]}>
          {data.map((entry, i) => (
            <rect key={i} fill={entry.color} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

/* ── AllocationDonut (simple bar-based) ─────────────────────────────────── */

export function AllocationBars({ positions }) {
  if (!positions?.length) return null

  const palette = [COLORS.blue, COLORS.green, '#06b6d4', COLORS.amber, COLORS.purple, '#f97316']

  return (
    <div className="space-y-2.5">
      {positions.map((p, i) => {
        const label = p.asset_class.replace(/_/g, ' ')
          .replace(/\b\w/g, c => c.toUpperCase())
        const current = (p.current_weight * 100).toFixed(0)
        const target  = (p.target_weight  * 100).toFixed(0)
        const color   = palette[i % palette.length]

        return (
          <div key={p.asset_class}>
            <div className="flex justify-between text-[11px] mb-1 font-body">
              <span className="text-slate-400">{label}</span>
              <span className="font-mono text-slate-300">
                <span style={{ color }}>{current}%</span>
                <span className="text-slate-600"> / {target}%</span>
              </span>
            </div>
            <div className="h-1.5 bg-bg-border rounded-full overflow-hidden relative">
              {/* Target marker */}
              <div
                className="absolute top-0 bottom-0 w-0.5 bg-slate-600"
                style={{ left: `${target}%` }}
              />
              {/* Current bar */}
              <div
                className="h-full rounded-full transition-all duration-700"
                style={{ width: `${current}%`, backgroundColor: color, opacity: 0.85 }}
              />
            </div>
          </div>
        )
      })}
      <p className="text-[10px] text-slate-600 mt-2 font-body">
        Colored bar = current · Line = Swensen target
      </p>
    </div>
  )
}
