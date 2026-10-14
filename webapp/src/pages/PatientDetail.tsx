import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api'
import { ChartBox, useChartStyle } from '../components/charts'
import { SessionModal } from '../components/SessionModal'
import { Badge, Card, Empty, ErrorBox, Loading, Modal, PageHeader, Stat, accuracyTone, useToast } from '../components/ui'
import { dateTime, duration, gameLabel, pct, shortDate, sig } from '../format'
import { useAsync } from '../hooks'
import type { Session } from '../types'
import { PatientForm } from './PatientForm'

export default function PatientDetail() {
  const { pid = '' } = useParams()
  const patient = useAsync(() => api.patient(pid), [pid])
  const progress = useAsync(() => api.progress(pid), [pid])
  const [editing, setEditing] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [selected, setSelected] = useState<Session>()
  const [game, setGame] = useState('')
  const chart = useChartStyle()
  const toast = useToast()
  const navigate = useNavigate()

  const sessions = useMemo(() => progress.data?.sessions ?? [], [progress.data])
  const games = useMemo(() => [...new Set(sessions.map((s) => s.game_name))], [sessions])
  const filtered = game ? sessions.filter((s) => s.game_name === game) : sessions
  const series = filtered.map((s, i) => ({ n: i + 1, label: shortDate(s.started_at), score: s.total_score, accuracy: s.accuracy * 100, game: gameLabel(s.game_name) }))
  const latest = sessions[sessions.length - 1]
  const first = sessions[0]
  const delta = latest && first && sessions.length > 1 ? latest.accuracy - first.accuracy : null

  const remove = async () => {
    try {
      await api.deletePatient(pid)
      toast(`Patient ${pid} and their sessions were deleted`, 'good')
      navigate('/patients')
    } catch (e) {
      toast((e as Error).message, 'bad')
    }
  }

  if (patient.error) {
    return (
      <>
        <PageHeader title={pid} />
        <ErrorBox error={patient.error} onRetry={patient.reload} />
        <p>
          <Link to="/patients">← Back to patients</Link>
        </p>
      </>
    )
  }
  const p = patient.data

  return (
    <>
      <PageHeader
        title={`Patient ${pid}`}
        subtitle={
          p ? (
            <>
              {p.age ? `Age ${p.age}` : 'Age not recorded'} · {p.affected_side ? `${p.affected_side} side affected` : 'Affected side not recorded'}
              {p.stroke_date && ` · Stroke on ${p.stroke_date}`}
            </>
          ) : (
            'Loading…'
          )
        }
        actions={
          <>
            <Link className="btn" to={`/games?patient=${encodeURIComponent(pid)}`}>
              Start game
            </Link>
            {sessions.length > 0 && (
              <a className="btn" href={api.exportUrl(pid)} download>
                Export CSV
              </a>
            )}
            <button className="btn" onClick={() => setEditing(true)} disabled={!p}>
              Edit
            </button>
            <button className="btn btn-danger" onClick={() => setConfirmDelete(true)}>
              Delete
            </button>
          </>
        }
      />
      {p?.notes && (
        <Card title="Clinical notes">
          <p className="notes">{p.notes}</p>
        </Card>
      )}
      {progress.error && <ErrorBox error={progress.error} onRetry={progress.reload} />}
      {progress.loading && !progress.data && <Loading />}
      {progress.data && sessions.length === 0 && (
        <Card>
          <Empty title="No sessions recorded yet">
            <Link to={`/games?patient=${encodeURIComponent(pid)}`}>Start a game</Link> for this patient. The session is saved when the game window closes.
          </Empty>
        </Card>
      )}
      {progress.data && sessions.length > 0 && (
        <>
          <div className="stats">
            <Stat label="Sessions" value={sessions.length} hint={`Since ${shortDate(first.started_at)}`} />
            <Stat label="Latest score" value={latest.total_score} hint={gameLabel(latest.game_name)} />
            <Stat label="Latest accuracy" value={pct(latest.accuracy)} hint={delta === null ? undefined : `${delta >= 0 ? '▲' : '▼'} ${pct(Math.abs(delta))} vs first session`} />
            <Stat label="Total therapy time" value={duration(sessions.reduce((a, s) => a + s.duration_s, 0))} />
          </div>

          <Card
            title="Progress over sessions"
            actions={
              games.length > 1 && (
                <select value={game} onChange={(e) => setGame(e.target.value)}>
                  <option value="">All games</option>
                  {games.map((g) => (
                    <option key={g} value={g}>
                      {gameLabel(g)}
                    </option>
                  ))}
                </select>
              )
            }
          >
            <div className="grid-2 flush">
              <div>
                <h3 className="section-title">Score</h3>
                <ChartBox height={240}>
                  <LineChart data={series}>
                    <CartesianGrid {...chart.grid} />
                    <XAxis dataKey="n" {...chart.axis} />
                    <YAxis {...chart.axis} width={40} />
                    <Tooltip {...chart.tooltip} labelFormatter={(n, pl) => `Session ${n} · ${pl?.[0]?.payload?.label ?? ''} · ${pl?.[0]?.payload?.game ?? ''}`} />
                    <Line type="monotone" dataKey="score" name="Score" stroke={chart.color(0)} strokeWidth={2} dot={{ r: 3 }} />
                  </LineChart>
                </ChartBox>
              </div>
              <div>
                <h3 className="section-title">Accuracy</h3>
                <ChartBox height={240}>
                  <LineChart data={series}>
                    <CartesianGrid {...chart.grid} />
                    <XAxis dataKey="n" {...chart.axis} />
                    <YAxis domain={[0, 100]} unit="%" {...chart.axis} width={44} />
                    <Tooltip {...chart.tooltip} formatter={(v: number) => `${v.toFixed(0)}%`} labelFormatter={(n) => `Session ${n}`} />
                    <Line type="monotone" dataKey="accuracy" name="Accuracy" stroke={chart.color(1)} strokeWidth={2} dot={{ r: 3 }} />
                  </LineChart>
                </ChartBox>
              </div>
            </div>
          </Card>

          <div className="grid-2">
            <Card title="Accuracy by target movement">
              {progress.data.movement_accuracy.length === 0 ? (
                <Empty title="No attempts recorded" />
              ) : (
                <ChartBox height={260}>
                  <BarChart data={progress.data.movement_accuracy.map((m) => ({ ...m, accuracy: m.accuracy * 100 }))}>
                    <CartesianGrid {...chart.grid} />
                    <XAxis dataKey="target_movement" {...chart.axis} />
                    <YAxis domain={[0, 100]} unit="%" {...chart.axis} width={44} />
                    <Tooltip {...chart.tooltip} formatter={(v: number) => `${v.toFixed(0)}%`} />
                    <Bar dataKey="accuracy" name="Accuracy" fill={chart.color(0)} radius={[4, 4, 0, 0]} maxBarSize={40} />
                  </BarChart>
                </ChartBox>
              )}
            </Card>
            <Card title="EMG activity by camera-detected movement">
              {progress.data.emg_activity_by_movement.length === 0 ? (
                <Empty title="No EMG activity recorded">Play in “Webcam + EMG sensor” mode to record RMS/MAV activity features.</Empty>
              ) : (
                <ChartBox height={260}>
                  <BarChart data={progress.data.emg_activity_by_movement}>
                    <CartesianGrid {...chart.grid} />
                    <XAxis dataKey="movement" {...chart.axis} />
                    <YAxis {...chart.axis} width={48} tickFormatter={(v) => sig(v)} />
                    <Tooltip {...chart.tooltip} formatter={(v: number) => sig(v)} />
                    <Legend {...chart.legend} />
                    <Bar dataKey="mean_rms" name="Mean RMS" fill={chart.color(0)} radius={[4, 4, 0, 0]} maxBarSize={28} />
                    <Bar dataKey="mean_mav" name="Mean MAV" fill={chart.color(2)} radius={[4, 4, 0, 0]} maxBarSize={28} />
                  </BarChart>
                </ChartBox>
              )}
              <p className="caption">RMS/MAV are electrical activity indicators, not clinical muscle-strength scores.</p>
            </Card>
          </div>

          <Card title="Session history">
            <div className="table-wrap">
              <table className="table table-click">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Date</th>
                    <th>Game</th>
                    <th className="r">Score</th>
                    <th className="r">Duration</th>
                    <th className="r">Accuracy</th>
                  </tr>
                </thead>
                <tbody>
                  {[...sessions].reverse().map((s) => (
                    <tr key={s.session_id} onClick={() => setSelected(s)}>
                      <td>{s.session_id}</td>
                      <td>{dateTime(s.started_at)}</td>
                      <td>{gameLabel(s.game_name)}</td>
                      <td className="r">{s.total_score}</td>
                      <td className="r">{duration(s.duration_s)}</td>
                      <td className="r">
                        <Badge tone={accuracyTone(s.accuracy)}>{pct(s.accuracy)}</Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}

      {selected && <SessionModal session={selected} onClose={() => setSelected(undefined)} />}
      {editing && p && (
        <Modal title={`Edit ${pid}`} onClose={() => setEditing(false)}>
          <PatientForm
            initial={p}
            onCancel={() => setEditing(false)}
            onSaved={() => {
              setEditing(false)
              toast('Patient updated', 'good')
              patient.reload()
            }}
          />
        </Modal>
      )}
      {confirmDelete && (
        <Modal title={`Delete patient ${pid}?`} onClose={() => setConfirmDelete(false)}>
          <p>
            This permanently deletes the patient record and all <strong>{sessions.length}</strong> recorded session(s) and their attempts. Export the CSV first if you need
            to keep the data.
          </p>
          <div className="form-actions">
            <button className="btn" onClick={() => setConfirmDelete(false)}>
              Cancel
            </button>
            <button className="btn btn-danger-solid" onClick={remove}>
              Delete permanently
            </button>
          </div>
        </Modal>
      )}
    </>
  )
}
