import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { emgBadge, emgTone } from '../format'
import { useAsync } from '../hooks'
import type { CameraCheck, EmgReport } from '../types'
import { Badge } from './ui'

type Result<T> = { data?: T; error?: string }

/** Pre-flight check on the Game Launcher: is the hardware the chosen input mode needs actually working? */
export function HardwareCheck({ mode, disabled }: { mode: string; disabled?: boolean }) {
  const needsEmg = mode === 'live'
  const needsCamera = mode === 'vision' || mode === 'live' || mode === 'replay'
  const ports = useAsync(() => api.hardwarePorts(), [], 5000)
  const [emg, setEmg] = useState<Result<EmgReport>>()
  const [camera, setCamera] = useState<Result<CameraCheck>>()
  const [testing, setTesting] = useState(false)

  const test = async () => {
    setTesting(true)
    const run = async <T,>(needed: boolean, fn: () => Promise<T>, set: (r: Result<T> | undefined) => void) => {
      if (!needed) return set(undefined)
      try {
        set({ data: await fn() })
      } catch (e) {
        set({ error: (e as Error).message })
      }
    }
    await Promise.all([run(needsEmg, () => api.emgCheck(), setEmg), run(needsCamera, () => api.cameraCheck(), setCamera)])
    setTesting(false)
  }

  // Test automatically when a hardware mode is chosen, but not while a game holds the devices.
  useEffect(() => {
    setEmg(undefined)
    setCamera(undefined)
    if ((needsEmg || needsCamera) && !disabled) test()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, disabled])

  if (!needsEmg && !needsCamera) return null
  const p = ports.data

  let emgState: [string, 'good' | 'warn' | 'bad' | 'info' | 'neutral'] = ['Checking…', 'neutral']
  if (emg?.error) emgState = ['Not working', 'bad']
  else if (emg?.data) emgState = [emgBadge(emg.data), emgTone(emg.data)]
  else if (p && !p.configured_present) emgState = ['Not plugged in', 'bad']
  else if (!testing) emgState = ['Not tested', 'neutral']

  let camState: [string, 'good' | 'warn' | 'bad' | 'info' | 'neutral'] = ['Checking…', 'neutral']
  if (camera?.error) camState = ['Not working', 'bad']
  else if (camera?.data) camState = camera.data.dark ? ['Picture is dark', 'warn'] : [`Working · ${camera.data.width}×${camera.data.height}`, 'good']
  else if (!testing) camState = ['Not tested', 'neutral']

  const problem = emg?.error ?? (emg?.data && emg.data.status !== 'streaming' ? emg.data.message : undefined) ?? camera?.error

  return (
    <div className="hw-check">
      <div className="hw-check-row">
        {needsEmg && (
          <span className="hw-item">
            <span className="field-label">EMG sensor{p ? ` (${p.configured_port})` : ''}</span> <Badge tone={emgState[1]}>{emgState[0]}</Badge>
          </span>
        )}
        {needsCamera && (
          <span className="hw-item">
            <span className="field-label">Webcam{p ? ` (camera ${p.camera_index})` : ''}</span> <Badge tone={camState[1]}>{camState[0]}</Badge>
          </span>
        )}
        <span className="hw-check-actions">
          <button className="btn btn-sm" onClick={test} disabled={testing || disabled}>
            {testing ? 'Testing…' : 'Test again'}
          </button>
          <Link to="/hardware" className="small">
            Hardware page →
          </Link>
        </span>
      </div>
      {disabled && <p className="muted small">The devices are in use by the running game.</p>}
      {problem && <p className="field-error">{problem}</p>}
      {emg?.data?.warnings.map((w) => (
        <p key={w} className="muted small">
          {w}
        </p>
      ))}
    </div>
  )
}
