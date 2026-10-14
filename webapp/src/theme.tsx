import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

type Mode = 'light' | 'dark' | 'system'

const PALETTES = {
  light: {
    series: ['#0f766e', '#2563eb', '#d97706', '#9333ea', '#dc2626', '#0891b2', '#65a30d', '#db2777'],
    grid: '#e2e8f0',
    axis: '#64748b',
    tooltipBg: '#ffffff',
    tooltipBorder: '#e2e8f0',
    text: '#0f172a',
  },
  dark: {
    series: ['#2dd4bf', '#60a5fa', '#fbbf24', '#c084fc', '#f87171', '#22d3ee', '#a3e635', '#f472b6'],
    grid: '#273449',
    axis: '#94a3b8',
    tooltipBg: '#111a2b',
    tooltipBorder: '#273449',
    text: '#e2e8f0',
  },
}

export type Palette = (typeof PALETTES)['light']

interface ThemeCtx {
  mode: Mode
  resolved: 'light' | 'dark'
  setMode: (m: Mode) => void
  palette: Palette
}

const Ctx = createContext<ThemeCtx | null>(null)

const readMode = (): Mode => {
  try {
    const v = localStorage.getItem('rehabhub.theme')
    return v === 'light' || v === 'dark' ? v : 'system'
  } catch {
    return 'system'
  }
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<Mode>(readMode)
  const [systemDark, setSystemDark] = useState(() => window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false)

  useEffect(() => {
    const mq = window.matchMedia?.('(prefers-color-scheme: dark)')
    if (!mq) return
    const fn = (e: MediaQueryListEvent) => setSystemDark(e.matches)
    mq.addEventListener('change', fn)
    return () => mq.removeEventListener('change', fn)
  }, [])

  const resolved = mode === 'system' ? (systemDark ? 'dark' : 'light') : mode

  useEffect(() => {
    if (mode === 'system') document.documentElement.removeAttribute('data-theme')
    else document.documentElement.setAttribute('data-theme', mode)
  }, [mode])

  const value = useMemo<ThemeCtx>(
    () => ({
      mode,
      resolved,
      palette: PALETTES[resolved],
      setMode: (m) => {
        setModeState(m)
        try {
          localStorage.setItem('rehabhub.theme', m)
        } catch {
          /* ignore */
        }
      },
    }),
    [mode, resolved],
  )
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useTheme() {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useTheme must be used inside ThemeProvider')
  return ctx
}
