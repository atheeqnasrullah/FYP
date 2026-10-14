import { Link } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, Line, LineChart, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api'
import { ChartBox, useChartStyle } from '../components/charts'
import { Icon } from '../components/Icon'
import { Badge, Card, Empty, ErrorBox, Loading, PageHeader, Stat, accuracyTone, useToast } from '../components/ui'
import { dateTime, duration, gameLabel, num, pct, shortDate } from '../format'
import { useAsync } from '../hooks'

export default function Dashboard() {
  const { data, error, loading, reload } = useAsync(() => api.overview(), [], 20000)
  const chart = useChartStyle()
  const toast = useToast()

  const sync = async () => {
    try {
      const r = await api.syncPending()
      toast(`Imported ${r.imported} offline session(s)${r.failed ? `, ${r.failed} failed` : ''}`, r.failed ? 'bad' : 'good')
      reload()
    } catch (e) {
      toast((e as Error).message, 'bad')
    }
  }

  return (
    <>
      <PageHeader
        title="Dashboard"
        subtitle="Overview of patients, rehabilitation game sessions and movement performance."
        actions={
          <Link className="btn btn-primary" to="/games">
            <Icon name="games" /> Start a game
          </Link>
        }
      />
      {error && <ErrorBox error={error} onRetry={reload} />}
      {loading && !data && !error && <Loading />}
      {data && (
        <>
          {data.pending_sessions > 0 && (
            <div className="notice">
              <span>
                {data.pending_sessions} session(s) were saved offline while the API was unreachable.
              </span>
              <button className="btn btn-sm btn-primary" onClick={sync}>
                Import now
              </button>
            </div>
          )}
          <div className="stats">
            <Stat label="Patients" value={num(data.patients)} icon={<Icon name="patients" />} />
            <Stat label="Sessions" value={num(data.sessions)} hint={`${num(data.attempts)} movement attempts`} icon={<Icon name="sessions" />} />
            <Stat label="Average accuracy" value={pct(data.avg_accuracy)} icon={<Icon name="target" />} />
            <Stat
              label="Therapy time"
              value={`${num(data.total_minutes, 0)} min`}
              hint={data.avg_reaction_ms ? `Avg reaction ${num(data.avg_reaction_ms)} ms` : undefined}
              icon={<Icon name="clock" />}
            />
          </div>

          {data.sessions === 0 ? (
            <Card>
              <Empty title="No sessions recorded yet">
                Add a patient and start a game from the <Link to="/games">Game Launcher</Link>. Sessions are saved when the game window closes.
              </Empty>
            </Card>
          ) : (
            <>
              <div className="grid-2">
                <Card title="Sessions per day">
                  <ChartBox>
                    <BarChart data={data.daily.map((d) => ({ ...d, label: shortDate(d.day) }))}>
                      <CartesianGrid {...chart.grid} />
                      <XAxis dataKey="label" {...chart.axis} />
                      <YAxis allowDecimals={false} {...chart.axis} width={32} />
                      <Tooltip {...chart.tooltip} />
                      <Bar dataKey="sessions" name="Sessions" fill={chart.color(0)} radius={[4, 4, 0, 0]} maxBarSize={36} />
                    </BarChart>
                  </ChartBox>
                </Card>
                <Card title="Daily average accuracy">
                  <ChartBox>
                    <LineChart data={data.daily.map((d) => ({ ...d, label: shortDate(d.day), accuracy: d.accuracy * 100 }))}>
                      <CartesianGrid {...chart.grid} />
                      <XAxis dataKey="label" {...chart.axis} />
                      <YAxis domain={[0, 100]} unit="%" {...chart.axis} width={44} />
                      <Tooltip {...chart.tooltip} formatter={(v: number) => `${v.toFixed(0)}%`} />
                      <Line type="monotone" dataKey="accuracy" name="Accuracy" stroke={chart.color(1)} strokeWidth={2} dot={{ r: 3 }} />
                    </LineChart>
                  </ChartBox>
                </Card>
              </div>
              <div className="grid-2">
                <Card title="Accuracy by target movement">
                  <ChartBox>
                    <BarChart data={data.movement_accuracy.map((m) => ({ ...m, accuracy: m.accuracy * 100 }))} layout="vertical" margin={{ left: 16 }}>
                      <CartesianGrid {...chart.grid} horizontal={false} vertical />
                      <XAxis type="number" domain={[0, 100]} unit="%" {...chart.axis} />
                      <YAxis type="category" dataKey="target_movement" {...chart.axis} width={90} />
                      <Tooltip {...chart.tooltip} formatter={(v: number) => `${v.toFixed(0)}%`} />
                      <Bar dataKey="accuracy" name="Accuracy" fill={chart.color(0)} radius={[0, 4, 4, 0]} maxBarSize={22} />
                    </BarChart>
                  </ChartBox>
                </Card>
                <Card title="Games played">
                  <div className="table-wrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Game</th>
                        <th className="r">Sessions</th>
                        <th className="r">Avg score</th>
                        <th className="r">Accuracy</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.sessions_by_game.map((g) => (
                        <tr key={g.game_name}>
                          <td>{gameLabel(g.game_name)}</td>
                          <td className="r">{g.sessions}</td>
                          <td className="r">{num(g.avg_score, 1)}</td>
                          <td className="r">
                            <Badge tone={accuracyTone(g.accuracy)}>{pct(g.accuracy)}</Badge>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  </div>
                </Card>
              </div>
              <Card title="Recent sessions" actions={<Link to="/sessions">View all →</Link>}>
                <div className="table-wrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Patient</th>
                        <th>Game</th>
                        <th className="r">Score</th>
                        <th className="r">Duration</th>
                        <th className="r">Accuracy</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.recent_sessions.map((s) => (
                        <tr key={s.session_id}>
                          <td>{dateTime(s.started_at)}</td>
                          <td>
                            <Link to={`/patients/${s.patient_id}`}>{s.patient_id}</Link>
                          </td>
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
        </>
      )}
    </>
  )
}
