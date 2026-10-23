import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { Card, ErrorBox, Loading, PageHeader, useToast } from '../components/ui'
import { HardwareCheck } from '../components/HardwareCheck'
import { pct, relativeDay } from '../format'
import { useAsync } from '../hooks'
import { PATIENT_RE } from './PatientForm'

const DIFFICULTY: Record<string, { label: string; help: string }> = {
  auto: { label: 'Auto', help: 'Adapts to the patient: harder after several successes, easier after misses. The level is remembered for next time.' },
  easy: { label: 'Easy', help: 'Slow and forgiving: bigger targets, less reach needed.' },
  medium: { label: 'Medium', help: 'Moderate speed and precision.' },
  hard: { label: 'Hard', help: 'Fast, smaller targets, more reach needed.' },
}
const DURATIONS = [
  { value: 60, label: '1 min' },
  { value: 120, label: '2 min' },
  { value: 180, label: '3 min' },
  { value: 300, label: '5 min' },
  { value: 600, label: '10 min' },
  { value: 0, label: 'No limit' },
]
const EFFORTS = [
  { value: 'auto', label: 'Auto' },
  { value: '20', label: '20%' },
  { value: '35', label: '35%' },
  { value: '50', label: '50%' },
  { value: '65', label: '65%' },
  { value: '0', label: 'Off' },
]
const EFFORT_MODES = ['live', 'replay']

function levelPace(days: number) {
  if (days === 0) return 'passing a level opens the next one straight away'
  if (days === 1) return 'one new level opens each day after a pass'
  return `a new level opens ${days} days after a pass`
}

function opensText(iso: string) {
  const day = new Date(`${iso}T00:00:00`)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const diff = Math.round((day.getTime() - today.getTime()) / 86400000)
  if (diff <= 0) return 'today'
  if (diff === 1) return 'tomorrow'
  return day.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' })
}
const MODE_HELP: Record<string, string> = {
  vision: 'The webcam follows the hand; its picture appears behind the game.',
  live: 'Webcam controls the game; the EMG sensor adds muscle-activity readings. The game waits for sensor data.',
  replay: 'Webcam controls the game; muscle-activity readings come from a recorded healthy volunteer, so no sensor is needed.',
  keyboard: 'Camera off. Arrow keys, O (open) and C (close).',
  sim: 'Simulated movements, for demonstrations without hardware.',
}

function elapsed(iso: string, now: number) {
  const s = Math.max(0, Math.floor((now - new Date(iso).getTime()) / 1000))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

export default function Games() {
  const [params] = useSearchParams()
  const info = useAsync(() => api.games(), [])
  const patients = useAsync(() => api.patients(), [])
  const status = useAsync(() => api.gameStatus(), [], 2000)
  const [showLog, setShowLog] = useState(false)
  const log = useAsync(() => api.gameLog(), [showLog], showLog && status.data?.running ? 3000 : undefined)
  const [game, setGame] = useState('balloon')
  const [mode, setMode] = useState('vision')
  const [difficulty, setDifficulty] = useState('auto')
  const [duration, setDuration] = useState(180)
  const [effort, setEffort] = useState('auto')
  const [level, setLevel] = useState('choose')
  const [patient, setPatient] = useState(params.get('patient') ?? '')
  const [busy, setBusy] = useState(false)
  const [now, setNow] = useState(Date.now())
  const toast = useToast()

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(id)
  }, [])

  const selected = info.data?.games.find((g) => g.id === game)
  useEffect(() => {
    if (selected && !selected.modes.includes(mode)) setMode(selected.modes[0])
  }, [selected, mode])

  const recent = useMemo(
    () => [...(patients.data ?? [])].sort((a, b) => (b.last_session ?? '').localeCompare(a.last_session ?? '')).slice(0, 6),
    [patients.data],
  )
  useEffect(() => {
    if (!patient && recent.length) setPatient(recent[0].patient_id)
  }, [recent, patient])

  const running = status.data?.running
  const last = status.data?.last
  const validPatient = PATIENT_RE.test(patient)
  const known = patients.data?.find((p) => p.patient_id === patient)
  const levels = useAsync(() => (validPatient ? api.gameLevels(patient) : Promise.resolve(null)), [patient, validPatient, running])
  const levelRows = levels.data?.games[game] ?? []
  const levelsDone = levelRows.filter((r) => r.state === 'passed').length
  const nextLevel = levelRows.find((r) => r.state !== 'passed')
  // A level picked for one patient or game may be locked for another.
  useEffect(() => setLevel('choose'), [patient, game])
  const levelLabel = level === 'choose' ? 'level chosen in game' : level === 'free' ? 'free play' : `level ${level}`

  const start = async () => {
    setBusy(true)
    try {
      await api.launchGame(game, mode, patient, difficulty, duration, effort, level)
      toast(`${selected?.name} started: play in the game window on this computer`, 'good')
      status.reload()
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
    } catch (e) {
      toast((e as Error).message, 'bad')
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <PageHeader title="Game Launcher" subtitle="Choose a patient and a game. The game window opens on the computer running RehabHub." />
      {info.error && <ErrorBox error={info.error} onRetry={info.reload} />}
      {info.loading && !info.data && <Loading />}

      {running && last && (
        <section className="live-card" aria-live="polite">
          <img src={`./games/${last.game}.jpg`} alt="" />
          <div className="live-body">
            <span className="live-label">
              <span className="live-dot" /> Game running
            </span>
            <h2>
              {last.game_name} <span className="muted">for</span> <Link to={`/patients/${last.patient_id}`}>{last.patient_id}</Link>
            </h2>
            <p className="muted">
              {info.data?.modes[last.mode]} · {DIFFICULTY[last.difficulty ?? 'auto']?.label ?? last.difficulty} ·{' '}
              {last.duration_s ? `${Math.round(last.duration_s / 60)} min session` : 'no time limit'}
              {last.level && last.level !== 'choose' && ` · ${last.level === 'free' ? 'free play' : `level ${last.level}`}`}
              {EFFORT_MODES.includes(last.mode) && last.effort && ` · grip ${last.effort === 'auto' ? 'auto' : last.effort === '0' ? 'off' : `${last.effort}%`}`}
            </p>
            <p className="small muted">In the game window: Enter pauses, M mutes, Esc finishes early and saves.</p>
          </div>
          <div className="live-side">
            <span className="live-timer">{elapsed(last.started_at, now)}</span>
            <button className="btn btn-danger-solid" onClick={stop} disabled={busy}>
              Stop game
            </button>
            <span className="muted small">Stopping here does not save the session.</span>
          </div>
        </section>
      )}
      {!running && last && (
        <div className={`last-run ${last.exit_code ? 'last-run-bad' : ''}`}>
          {last.exit_code ? (
            <span>
              The last game ({last.game_name}) closed with an error. <button className="link-btn" onClick={() => setShowLog(true)}>Show the game log</button>
            </span>
          ) : (
            <span>
              {last.game_name} with {last.patient_id} finished. <Link to={`/patients/${last.patient_id}`}>See {last.patient_id}'s progress →</Link>
            </span>
          )}
        </div>
      )}

      {info.data && (
        <>
          <Card title={<StepTitle n={1} text="Patient" />}>
            <div className="patient-pick">
              {recent.map((p) => (
                <button key={p.patient_id} className={`pick ${p.patient_id === patient ? 'selected' : ''}`} onClick={() => setPatient(p.patient_id)} aria-pressed={p.patient_id === patient}>
                  <strong>{p.patient_id}</strong>
                  <span className="muted small">{p.sessions ? `${relativeDay(p.last_session)} · ${pct(p.avg_accuracy)}` : 'No sessions yet'}</span>
                </button>
              ))}
              <label className="pick-input">
                <span className="small muted">Other patient code</span>
                <input list="patient-codes" value={patient} onChange={(e) => setPatient(e.target.value.trim())} placeholder="P05" />
                <datalist id="patient-codes">
                  {patients.data?.map((p) => (
                    <option key={p.patient_id} value={p.patient_id} />
                  ))}
                </datalist>
              </label>
            </div>
            {patient && !validPatient && <p className="field-error">Code must start with P and use only letters, numbers, _ or -.</p>}
            {validPatient && !known && <p className="muted small">New code: a patient record is created when the session is saved.</p>}
          </Card>

          <Card title={<StepTitle n={2} text="Game" />}>
            <div className="game-grid">
              {info.data.games.map((g) => (
                <button key={g.id} className={`game-card ${g.id === game ? 'selected' : ''}`} onClick={() => setGame(g.id)} aria-pressed={g.id === game}>
                  <img src={`./games/${g.id}.jpg`} alt={`${g.name} screenshot`} />
                  <div className="game-card-body">
                    <strong>{g.name}</strong>
                    <span className="muted">{g.description}</span>
                    {g.trains && (
                      <span className="tags">
                        {g.trains.map((t) => (
                          <span key={t} className="tag">
                            {t}
                          </span>
                        ))}
                      </span>
                    )}
                  </div>
                </button>
              ))}
            </div>
          </Card>

          <Card title={<StepTitle n={3} text="Settings" />}>
            <div className="settings-grid">
              <label>
                <span className="field-label">Input</span>
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
                <span className="field-label">Level</span>
                <div className="segmented">
                  <button type="button" className={level === 'choose' ? 'active' : ''} onClick={() => setLevel('choose')}>
                    Choose in game
                  </button>
                  {levelRows.map((r) => (
                    <button
                      key={r.level}
                      type="button"
                      className={`${String(r.level) === level ? 'active' : ''} ${r.state === 'passed' ? 'passed' : ''}`}
                      disabled={r.state === 'waiting' || r.state === 'locked'}
                      title={`${r.name}: ${r.goal}${r.state === 'passed' ? ` · passed, ${r.stars} star${r.stars === 1 ? '' : 's'}` : r.state === 'waiting' && r.opens_on ? ` · opens ${opensText(r.opens_on)}` : r.state === 'locked' ? ' · pass the previous level first' : ''}`}
                      onClick={() => setLevel(String(r.level))}
                    >
                      {r.state === 'passed' ? `${r.level} ✓` : r.level}
                    </button>
                  ))}
                  <button type="button" className={level === 'free' ? 'active' : ''} onClick={() => setLevel('free')}>
                    Free play
                  </button>
                </div>
                <small className="muted">
                  {!validPatient
                    ? 'Choose a patient to see their levels.'
                    : levels.data
                      ? `${levelsDone} of 7 levels done in ${selected?.name ?? 'this game'}${
                          nextLevel ? ` · next: level ${nextLevel.level} (${nextLevel.goal.toLowerCase()})${nextLevel.state === 'waiting' && nextLevel.opens_on ? `, opens ${opensText(nextLevel.opens_on)}` : ''}` : ''
                        } · ${levelPace(levels.data.days_between)}.`
                      : 'Loading levels…'}
                  {level === 'choose' && ' The patient picks a level on the first screen of the game.'}
                </small>
              </label>
              {(level === 'choose' || level === 'free') && (
              <label>
                <span className="field-label">{level === 'free' ? 'Difficulty' : 'Free-play difficulty'}</span>
                <div className="segmented">
                  {Object.entries(DIFFICULTY).map(([d, v]) => (
                    <button key={d} type="button" className={d === difficulty ? 'active' : ''} onClick={() => setDifficulty(d)}>
                      {v.label}
                    </button>
                  ))}
                </div>
                <small className="muted">{DIFFICULTY[difficulty].help} Levels 1-7 set their own difficulty.</small>
              </label>
              )}
              <label>
                <span className="field-label">Session length</span>
                <div className="segmented">
                  {DURATIONS.map((d) => (
                    <button key={d.value} type="button" className={d.value === duration ? 'active' : ''} onClick={() => setDuration(d.value)}>
                      {d.label}
                    </button>
                  ))}
                </div>
              </label>
              {EFFORT_MODES.includes(mode) && (
                <label>
                  <span className="field-label">Grip effort needed</span>
                  <div className="segmented">
                    {EFFORTS.map((e) => (
                      <button key={e.value} type="button" className={e.value === effort ? 'active' : ''} onClick={() => setEffort(e.value)}>
                        {e.label}
                      </button>
                    ))}
                  </div>
                  <small className="muted">
                    {effort === 'auto'
                      ? 'A pop, brake, gold grab or shape pick-up counts only above a share of the patient’s strongest squeeze (measured at the start); Auto raises it from 25% to 60% as the level rises.'
                      : effort === '0'
                        ? 'No minimum: any fist the camera sees counts. Effort is still recorded.'
                        : `A grip action counts only at ${effort}% or more of the patient’s strongest squeeze, measured at the start of the session.`}
                  </small>
                </label>
              )}
            </div>
            <HardwareCheck mode={mode} disabled={!!running} />
          </Card>

          <div className="start-bar">
            <div>
              <strong>{selected?.name}</strong>
              <span className="muted">
                {' '}
                for {validPatient ? patient : '—'} · {info.data.modes[mode]} · {levelLabel} · {DURATIONS.find((d) => d.value === duration)?.label}
              </span>
            </div>
            <button className="btn btn-primary btn-lg" onClick={start} disabled={busy || running || !validPatient}>
              {running ? 'A game is running' : `▶ Start ${selected?.name ?? ''}`}
            </button>
          </div>

          <details className="log-details" open={showLog} onToggle={(e) => setShowLog((e.target as HTMLDetailsElement).open)}>
            <summary>Technical game log</summary>
            {log.loading && !log.data ? <Loading /> : <pre className="log">{log.data?.lines.length ? log.data.lines.join('\n') : 'No log output yet.'}</pre>}
          </details>
        </>
      )}
    </>
  )
}

function StepTitle({ n, text }: { n: number; text: string }) {
  return (
    <span className="step-title">
      <span className="step-num">{n}</span> {text}
    </span>
  )
}

