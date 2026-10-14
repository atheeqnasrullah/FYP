import { Link, useNavigate } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, Line, LineChart, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api'
import { ChartBox, useChartStyle } from '../components/charts'
import { Icon } from '../components/Icon'
import { Sparkline, TrendChip } from '../components/Trend'
import { Badge, Card, Empty, ErrorBox, Loading, PageHeader, Stat, accuracyTone, useToast } from '../components/ui'
import { daysSince, gameLabel, movement, num, pct, relativeDay, shortDate } from '../format'
import { useAsync } from '../hooks'
import type { PatientSummary } from '../types'

interface Flag {
  patient: PatientSummary
  reason: string
  tone: 'bad' | 'warn' | 'info'
}

/** Patients a therapist should look at first, most urgent first. */
function attentionList(patients: PatientSummary[]): Flag[] {
  const flags: Flag[] = []
  for (const p of patients) {
    const idle = daysSince(p.last_session)
    if (!p.sessions) flags.push({ patient: p, reason: 'No sessions yet', tone: 'info' })
    else if (p.trend !== null && p.trend <= -0.1) flags.push({ patient: p, reason: `Accuracy down ${Math.round(-p.trend * 100)}% over the last 3 sessions`, tone: 'bad' })
    else if (idle !== null && idle >= 7) flags.push({ patient: p, reason: `No session for ${idle} days`, tone: 'warn' })
    else if (p.sessions >= 3 && (p.avg_accuracy ?? 1) < 0.5) flags.push({ patient: p, reason: `Average accuracy ${pct(p.avg_accuracy)}: consider an easier level`, tone: 'warn' })
  }
  const order = { bad: 0, warn: 1, info: 2 }
  return flags.sort((a, b) => order[a.tone] - order[b.tone])
}

function greeting() {
  const h = new Date().getHours()
  return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening'
}

export default function Dashboard() {
  const overview = useAsync(() => api.overview(), [], 20000)
  const patients = useAsync(() => api.patients(), [], 20000)
  const chart = useChartStyle()
  const toast = useToast()
  const navigate = useNavigate()
  const data = overview.data

  const sync = async () => {
    try {
      const r = await api.syncPending()
      toast(`Imported ${r.imported} offline session(s)${r.failed ? `, ${r.failed} failed` : ''}`, r.failed ? 'bad' : 'good')
      overview.reload()
    } catch (e) {
      toast((e as Error).message, 'bad')
    }
  }

  const flags = patients.data ? attentionList(patients.data) : []
  const today = new Date().toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' })
  const sortedPatients = [...(patients.data ?? [])].sort((a, b) => (b.last_session ?? '').localeCompare(a.last_session ?? ''))

  return (
    <>
      <PageHeader
        title={greeting()}
        subtitle={`${today}. Here is how your patients are doing.`}
        actions={
          <>
            <Link className="btn" to="/patients?add=1">
              + Add patient
            </Link>
            <Link className="btn btn-primary" to="/games">
              <Icon name="games" /> Start a session
            </Link>
          </>
        }
      />
      {overview.error && <ErrorBox error={overview.error} onRetry={overview.reload} />}
      {overview.loading && !data && !overview.error && <Loading />}
      {data && (
        <>
          {data.pending_sessions > 0 && (
            <div className="notice">
              <span>{data.pending_sessions} session(s) were saved on this computer while the API was offline.</span>
              <button className="btn btn-sm btn-primary" onClick={sync}>
                Import now
              </button>
            </div>
          )}
          <div className="stats">
            <Stat label="Patients" value={num(data.patients)} icon={<Icon name="patients" />} />
            <Stat label="Sessions" value={num(data.sessions)} hint={`${num(data.attempts)} movements practised`} icon={<Icon name="sessions" />} />
            <Stat label="Average accuracy" value={pct(data.avg_accuracy)} icon={<Icon name="target" />} />
            <Stat label="Therapy time" value={`${num(data.total_minutes, 0)} min`} hint={data.avg_reaction_ms ? `Avg reaction ${(data.avg_reaction_ms / 1000).toFixed(1)} s` : undefined} icon={<Icon name="clock" />} />
          </div>

          {data.patients === 0 ? (
            <Card>
              <div className="welcome">
                <h2>Welcome to RehabHub</h2>
                <p className="muted">Three steps to the first session:</p>
                <ol className="steps">
                  <li>
                    <strong>Add a patient</strong> with a coded ID such as P01.
                  </li>
                  <li>
                    <strong>Start a game</strong> from the Game Launcher; it opens on this computer.
                  </li>
                  <li>
                    <strong>Review progress</strong> here when the session ends.
                  </li>
                </ol>
                <Link className="btn btn-primary" to="/patients?add=1">
                  Add the first patient
                </Link>
              </div>
            </Card>
          ) : (
            <>
              <div className="grid-dash">
                <Card title="Needs attention" actions={<span className="muted small">{flags.length ? `${flags.length} patient${flags.length === 1 ? '' : 's'}` : ''}</span>}>
                  {patients.loading && !patients.data ? (
                    <Loading />
                  ) : flags.length === 0 ? (
                    <div className="all-good">
                      <span className="all-good-icon">✓</span>
                      <div>
                        <strong>Everyone is on track</strong>
                        <p className="muted small">No drops in accuracy and everyone was seen this week.</p>
                      </div>
                    </div>
                  ) : (
                    <ul className="flag-list">
                      {flags.map((f) => (
                        <li key={f.patient.patient_id} className={`flag flag-${f.tone}`}>
                          <div className="flag-main">
                            <Link to={`/patients/${f.patient.patient_id}`} className="flag-code">
                              {f.patient.patient_id}
                            </Link>
                            <span>{f.reason}</span>
                          </div>
                          <Link className="btn btn-sm" to={`/games?patient=${encodeURIComponent(f.patient.patient_id)}`}>
                            Start game
                          </Link>
                        </li>
                      ))}
                    </ul>
                  )}
                </Card>
                <Card title="Accuracy over time" actions={<span className="muted small">All patients, daily average</span>}>
                  {data.daily.length < 2 ? (
                    <Empty title="Not enough sessions yet">The trend appears after sessions on two different days.</Empty>
                  ) : (
                    <ChartBox height={240}>
                      <LineChart data={data.daily.map((d) => ({ ...d, label: shortDate(d.day), accuracy: d.accuracy * 100 }))}>
                        <CartesianGrid {...chart.grid} />
                        <XAxis dataKey="label" {...chart.axis} minTickGap={24} />
                        <YAxis domain={[0, 100]} unit="%" {...chart.axis} width={44} />
                        <Tooltip {...chart.tooltip} formatter={(v: number, _n, item) => [`${v.toFixed(0)}% (${item.payload.sessions} sessions)`, 'Accuracy']} />
                        <Line type="monotone" dataKey="accuracy" name="Accuracy" stroke={chart.color(0)} strokeWidth={2.5} dot={{ r: 3 }} />
                      </LineChart>
                    </ChartBox>
                  )}
                </Card>
              </div>

              <Card title="Patients" actions={<Link to="/patients">All patients →</Link>}>
                <div className="patient-grid">
                  {sortedPatients.slice(0, 8).map((p) => (
                    <button key={p.patient_id} className="patient-card" onClick={() => navigate(`/patients/${p.patient_id}`)}>
                      <div className="patient-card-top">
                        <strong>{p.patient_id}</strong>
                        <TrendChip trend={p.trend} />
                      </div>
                      <Sparkline values={p.recent_accuracy} width={170} height={36} />
                      <div className="patient-card-meta">
                        <span>{p.sessions ? <Badge tone={accuracyTone(p.avg_accuracy)}>{pct(p.avg_accuracy)}</Badge> : <Badge>New</Badge>}</span>
                        <span className="muted small">{relativeDay(p.last_session)}</span>
                      </div>
                      {p.last_game && <span className="muted small">Last: {gameLabel(p.last_game)}</span>}
                    </button>
                  ))}
                </div>
              </Card>

              <div className="grid-2">
                <Card title="Accuracy by movement">
                  <ChartBox height={260}>
                    <BarChart data={data.movement_accuracy.map((m) => ({ ...m, name: movement(m.target_movement), accuracy: m.accuracy * 100 }))} layout="vertical" margin={{ left: 8 }}>
                      <CartesianGrid {...chart.grid} horizontal={false} vertical />
                      <XAxis type="number" domain={[0, 100]} unit="%" {...chart.axis} />
                      <YAxis type="category" dataKey="name" {...chart.axis} width={100} />
                      <Tooltip {...chart.tooltip} formatter={(v: number, _n, item) => [`${v.toFixed(0)}% of ${item.payload.attempts}`, 'Accuracy']} />
                      <Bar dataKey="accuracy" name="Accuracy" fill={chart.color(0)} radius={[0, 4, 4, 0]} maxBarSize={20} />
                    </BarChart>
                  </ChartBox>
                </Card>
                <Card title="Games played">
                  <ul className="game-stats">
                    {data.sessions_by_game.map((g) => (
                      <li key={g.game_name}>
                        <img src={`./games/${gameThumb(g.game_name)}.jpg`} alt="" />
                        <div>
                          <strong>{gameLabel(g.game_name)}</strong>
                          <span className="muted small">
                            {g.sessions} session{g.sessions === 1 ? '' : 's'} · avg score {num(g.avg_score, 0)}
                          </span>
                        </div>
                        <Badge tone={accuracyTone(g.accuracy)}>{pct(g.accuracy)}</Badge>
                      </li>
                    ))}
                  </ul>
                </Card>
              </div>
            </>
          )}
        </>
      )}
    </>
  )
}

function gameThumb(gameName: string) {
  const n = gameName.toLowerCase()
  return n.includes('balloon') ? 'balloon' : n.includes('car') ? 'car' : n.includes('treasure') ? 'treasure' : 'shape'
}
