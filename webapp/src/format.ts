export const pct = (v: number | null | undefined, digits = 0) =>
  v === null || v === undefined || Number.isNaN(v) ? '—' : `${(v * 100).toFixed(digits)}%`

export const num = (v: number | null | undefined, digits = 0) =>
  v === null || v === undefined || Number.isNaN(v) ? '—' : v.toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits })

export const sig = (v: number | null | undefined) => {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  const a = Math.abs(v)
  if (a === 0) return '0'
  if (a >= 100) return v.toFixed(0)
  if (a >= 1) return v.toFixed(2)
  return v.toPrecision(3)
}

export const dateTime = (iso: string | null | undefined) => {
  if (!iso) return '—'
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

export const shortDate = (iso: string | null | undefined) => {
  if (!iso) return '—'
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

export const duration = (s: number) => {
  const m = Math.floor(s / 60)
  return m ? `${m}m ${s % 60}s` : `${s}s`
}

export const gameLabel = (name: string) => name.replace(/_/g, ' ')
