import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { Badge, Card, ErrorBox, Loading, PageHeader, useToast } from '../components/ui'
import { dateTime } from '../format'
import { useAsync } from '../hooks'
import { PATIENT_RE } from './PatientForm'

const GAME_ART: Record<string, string> = { balloon: '🎈', car: '🚗', treasure: '🗺️', shape: '🔷' }
const DIFFICULTY: Record<string, string> = {
  auto: 'Adapts to the patient: gets harder after several successes in a row and easier after misses. The level is remembered for the next session.',
  easy: 'Slow and forgiving: bigger targets, fewer obstacles.',
  medium: 'Moderate speed and precision.',
  hard: 'Fast, smaller targets and more obstacles.',
}
const DURATIONS = [
  { value: 60, label: '1 min' },
  { value: 120, label: '2 min' },
  { value: 180, label: '3 min' },
  { value: 300, label: '5 min' },
  { value: 600, label: '10 min' },
  { value: 0, label: 'No limit' },
]
const MODE_HELP: Record<string, string> = {
  vision: 'The webcam identifies hand gestures and movement direction; its video appears behind the game objects.',
  live: 'Webcam labels control the game; the EMG sensor adds RMS/MAV activity feedback. The window waits until fresh EMG data arrives.',
  keyboard: 'Camera stays off. Arrows move, O/C open/close, S/P rotate, Space rest, Esc quits.',
  sim: 'Simulated movement commands — useful for demos and testing without hardware.',
}

export default function Games() {
  const [params] = useSearchParams()
  const info = useAsync(() => api.games(), [])
  const patients = useAsync(() => api.patients(), [])
  const status = useAsync(() => api.gameStatus(), [], 3000)
  const log = useAsync(() => api.gameLog(), [], status.data?.running ? 3000 : undefined)
  const [game, setGame] = useState('balloon')
  const [mode, setMode] = useState('vision')
  const [patient, setPatient] = useState(params.get('patient') ?? '')
  const [difficulty, setDifficulty] = useState('auto')
  const [duration, setDuration] = useState(180)
  const [busy, setBusy] = useState(false)
  const toast = useToast()

  const selected = info.data?.games.find((g) => g.id === game)
  useEffect(() => {
    if (selected && !selected.modes.includes(mode)) setMode(selected.modes[0])
  }, [selected, mode])
  useEffect(() => {
    if (!patient && patients.data?.length) setPatient(patients.data[0].patient_id)
  }, [patients.data, patient])

  const running = status.data?.running
  const last = status.data?.last
  const validPatient = PATIENT_RE.test(patient)
  const known = patients.data?.some((p) => p.patient_id === patient)

  const start = async () => {
    setBusy(true)
    try {
      await api.launchGame(game, mode, patient, difficulty, duration)
      toast(`${selected?.name} started — play in the game window on this computer`, 'good')
      status.reload()
      log.reload()
    } catch (e) {
      toast((e as Error).message, 'bad')
    } finally {
      setBusy(false)
    }
  }
  const stop = async () => {
    setBusy(true)
    try {
      const r = await api.stopGame()
      toast(r.message, 'info')
      status.reload()
      log.reload()
    } catch (e) {
      toast((e as Error).message, 'bad')
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <PageHeader title="Game Launcher" subtitle="Start a rehabilitation game for a patient. The Pygame window opens on the computer running the API." />
      {info.error && <ErrorBox error={info.error} onRetry={info.reload} />}
      {info.loading && !info.data && <Loading />}
      {info.data && (
        <>
          <div className="game-grid">
            {info.data.games.map((g) => (
              <button key={g.id} className={`game-card ${g.id === game ? 'selected' : ''}`} onClick={() => setGame(g.id)} aria-pressed={g.id === game}>
                <span className="game-art" aria-hidden="true">
                  {GAME_ART[g.id] ?? '🎮'}
                </span>
                <strong>{g.name}</strong>
                <span className="muted">{g.description}</span>
              </button>
            ))}
          </div>

          <div className="grid-2">
            <Card title="Session setup">
              <div className="form">
                <label>
                  Input method
                  <div className="segmented">
                    {selected?.modes.map((m) => (
                      <button key={m} type="button" className={m === mode ? 'active' : ''} onClick={() => setMode(m)}>
                        {info.data!.modes[m]}
                      </button>
                    ))}
                  </div>
                  <small className="muted">{MODE_HELP[mode]}</small>
                </label>
                <label>
                  Difficulty
                  <div className="segmented">
                    {Object.keys(DIFFICULTY).map((d) => (
                      <button key={d} type="button" className={d === difficulty ? 'active' : ''} onClick={() => setDifficulty(d)}>
                        {d === 'auto' ? 'Auto (adaptive)' : d[0].toUpperCase() + d.slice(1)}
                      </button>
                    ))}
                  </div>
                  <small className="muted">{DIFFICULTY[difficulty]}</small>
                </label>
                <label>
                  Session length
                  <select value={duration} onChange={(e) => setDuration(Number(e.target.value))}>
                    {DURATIONS.map((d) => (
                      <option key={d.value} value={d.value}>
                        {d.label}
                      </option>
                    ))}
                  </select>
                  <small className="muted">The game shows a countdown timer and a results screen when time is up.</small>
                </label>
                <label>
                  Patient code
                  <input list="patient-codes" value={patient} onChange={(e) => setPatient(e.target.value.trim())} placeholder="P01" />
                  <datalist id="patient-codes">
                    {patients.data?.map((p) => (
                      <option key={p.patient_id} value={p.patient_id} />
                    ))}
                  </datalist>
                  <small className="muted">
                    {!patient
                      ? 'Choose an existing patient or type a new code.'
                      : !validPatient
                        ? 'Code must start with P and contain only letters, numbers, _ or -.'
                        : known
                          ? 'Existing patient.'
                          : 'New code — a patient record is created when the session is saved.'}
                  </small>
                </label>
                <div className="form-actions start">
                  <button className="btn btn-primary btn-lg" onClick={start} disabled={busy || running || !validPatient}>
                    ▶ Start {selected?.name}
                  </button>
                  <button className="btn btn-lg" onClick={stop} disabled={busy || !running}>
                    ■ Stop game
                  </button>
                </div>
              </div>
            </Card>

            <Card title="Status" actions={running ? <Badge tone="good">Running</Badge> : <Badge>Idle</Badge>}>
              {last ? (
                <dl className="kv">
                  <dt>Game</dt>
                  <dd>{last.game_name}</dd>
                  <dt>Patient</dt>
                  <dd>
                    <Link to={`/patients/${last.patient_id}`}>{last.patient_id}</Link>
                  </dd>
                  <dt>Mode</dt>
                  <dd>{info.data.modes[last.mode]}</dd>
                  {last.difficulty && (
                    <>
                      <dt>Difficulty</dt>
                      <dd>
                        {last.difficulty === 'auto' ? 'Auto (adaptive)' : last.difficulty[0].toUpperCase() + last.difficulty.slice(1)}
                        {last.duration_s !== undefined && ` · ${last.duration_s ? `${Math.round(last.duration_s / 60)} min` : 'no time limit'}`}
                      </dd>
                    </>
                  )}
                  <dt>Started</dt>
                  <dd>{dateTime(last.started_at)}</dd>
                  {running ? (
                    <>
                      <dt>Process</dt>
                      <dd>PID {status.data?.pid}</dd>
                    </>
                  ) : (
                    <>
                      <dt>Exit code</dt>
                      <dd>{last.exit_code ?? '—'}</dd>
                    </>
                  )}
                </dl>
              ) : (
                <p className="muted">No game has been launched from the web app since the API started.</p>
              )}
              <p className="caption">
                In the game: Enter pauses, M mutes sound, Esc finishes early and saves. Stopping from here ends the game without saving.
              </p>
            </Card>
          </div>

          <Card title="Game log" actions={<button className="btn btn-sm" onClick={log.reload}>Refresh</button>}>
            <pre className="log">{log.data?.lines.length ? log.data.lines.join('\n') : 'No log output yet.'}</pre>
          </Card>
        </>
      )}
    </>
  )
}
