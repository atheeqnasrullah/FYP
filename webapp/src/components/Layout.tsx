import { useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { api } from '../api'
import { useAsync } from '../hooks'
import { useTheme } from '../theme'
import { Icon } from './Icon'

const NAV = [
  { to: '/', label: 'Dashboard', icon: 'dashboard' },
  { to: '/patients', label: 'Patients', icon: 'patients' },
  { to: '/sessions', label: 'Sessions', icon: 'sessions' },
  { to: '/games', label: 'Game Launcher', icon: 'games' },
  { to: '/hardware', label: 'Hardware', icon: 'hardware' },
  { to: '/datasets', label: 'EMG Datasets', icon: 'datasets' },
  { to: '/settings', label: 'Settings', icon: 'settings' },
]

export function Layout() {
  const [open, setOpen] = useState(false)
  const { resolved, setMode } = useTheme()
  const health = useAsync(() => api.health(), [], 15000)
  const game = useAsync(() => api.gameStatus(), [], 5000)
  const hardware = useAsync(() => api.hardwarePorts(), [], 5000)
  const location = useLocation()
  const online = !health.error && health.data?.status === 'ok'

  return (
    <div className="shell">
      <aside className={`sidebar ${open ? 'open' : ''}`}>
        <div className="brand">
          <span className="brand-mark">
            <Icon name="pulse" size={20} />
          </span>
          <div>
            <strong>RehabHub</strong>
            <small>Stroke rehabilitation</small>
          </div>
        </div>
        <nav>
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === '/'} onClick={() => setOpen(false)} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
              <Icon name={n.icon} />
              <span>{n.label}</span>
              {n.to === '/games' && game.data?.running && <span className="live-dot" title="A game is running" />}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          {online && hardware.data && (
            <NavLink to="/hardware" onClick={() => setOpen(false)} className={`api-pill hw-pill ${hardware.data.configured_present ? 'ok' : 'down'}`} title="EMG sensor connection">
              <span className="dot" /> ESP32 {hardware.data.configured_present ? `on ${hardware.data.configured_port}` : 'not connected'}
            </NavLink>
          )}
          <div className={`api-pill ${online ? 'ok' : 'down'}`}>
            <span className="dot" /> API {health.loading && !health.data && !health.error ? 'checking…' : online ? 'online' : 'offline'}
          </div>
          <p className="disclaimer">Research prototype — not a certified medical device. Use coded patient IDs only.</p>
        </div>
      </aside>
      {open && <div className="scrim" onClick={() => setOpen(false)} />}
      <div className="main">
        <header className="topbar">
          <button className="icon-btn menu-btn" onClick={() => setOpen(true)} aria-label="Open navigation">
            <Icon name="menu" />
          </button>
          <span className="crumb">{NAV.find((n) => (n.to === '/' ? location.pathname === '/' : location.pathname.startsWith(n.to)))?.label}</span>
          <div className="topbar-right">
            {game.data?.running && game.data.last && (
              <NavLink to="/games" className="running-chip">
                <span className="live-dot" /> {game.data.last.game_name} · {game.data.last.patient_id}
              </NavLink>
            )}
            <button className="icon-btn" onClick={() => setMode(resolved === 'dark' ? 'light' : 'dark')} aria-label="Toggle theme" title="Toggle theme">
              <Icon name={resolved === 'dark' ? 'sun' : 'moon'} />
            </button>
          </div>
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
