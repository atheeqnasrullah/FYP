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

const MOVEMENTS: Record<string, string> = {
  Hand_Close: 'Close hand',
  Hand_Open: 'Open hand',
  Left: 'Move left',
  Right: 'Move right',
  Up: 'Move up',
  Down: 'Move down',
  Supination: 'Palm up',
  Pronation: 'Palm down',
  Rest: 'Rest',
  Missed: 'Missed',
}

/** Movement or shape label in plain words (Hand_Close -> Close hand). */
export const movement = (label: string | null | undefined) => (label ? (MOVEMENTS[label] ?? label.replace(/_/g, ' ')) : '—')

/** "today", "yesterday", "3 days ago", "2 weeks ago" … */
export const relativeDay = (iso: string | null | undefined, now = new Date()) => {
  if (!iso) return 'Never'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const days = Math.floor((new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime() - new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()) / 86400000)
  if (days <= 0) return 'Today'
  if (days === 1) return 'Yesterday'
  if (days < 14) return `${days} days ago`
  if (days < 60) return `${Math.round(days / 7)} weeks ago`
  return d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}

export const daysSince = (iso: string | null | undefined, now = new Date()) => {
  if (!iso) return null
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? null : Math.floor((now.getTime() - d.getTime()) / 86400000)
}
