import { pct } from '../format'

/** Tiny accuracy line for the last sessions, with the latest point emphasised. */
export function Sparkline({ values, width = 96, height = 28 }: { values: number[]; width?: number; height?: number }) {
  if (values.length < 2) return <span className="muted small">Not enough sessions</span>
  const pad = 3
  const x = (i: number) => pad + (i * (width - pad * 2)) / (values.length - 1)
  const y = (v: number) => pad + (1 - Math.max(0, Math.min(1, v))) * (height - pad * 2)
  const d = values.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ')
  const area = `${d} L${x(values.length - 1).toFixed(1)},${height - pad} L${x(0).toFixed(1)},${height - pad} Z`
  const last = values[values.length - 1]
  return (
    <svg className="sparkline" width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`Accuracy over the last ${values.length} sessions, latest ${pct(last)}`}>
      <path d={area} className="spark-area" />
      <path d={d} className="spark-line" />
      <circle cx={x(values.length - 1)} cy={y(last)} r={3} className="spark-dot" />
    </svg>
  )
}

/** Change in accuracy between the last three sessions and the three before. */
export function TrendChip({ trend }: { trend: number | null | undefined }) {
  if (trend === null || trend === undefined) return <span className="trend trend-flat">—</span>
  const points = Math.round(trend * 100)
  if (Math.abs(points) < 5) return <span className="trend trend-flat" title="Accuracy steady over the last sessions">Steady</span>
  return points > 0 ? (
    <span className="trend trend-up" title="Average of the last 3 sessions vs the 3 before">▲ {points}%</span>
  ) : (
    <span className="trend trend-down" title="Average of the last 3 sessions vs the 3 before">▼ {Math.abs(points)}%</span>
  )
}
