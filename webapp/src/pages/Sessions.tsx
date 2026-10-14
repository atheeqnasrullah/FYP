import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { SessionModal } from '../components/SessionModal'
import { Badge, Card, Empty, ErrorBox, Loading, Modal, PageHeader, accuracyTone, useToast } from '../components/ui'
import { dateTime, duration, gameLabel, pct } from '../format'
import { useAsync } from '../hooks'
import type { Session } from '../types'

export default function Sessions() {
  const { data, error, loading, reload } = useAsync(() => api.sessions(), [])
  const [patient, setPatient] = useState('')
  const [game, setGame] = useState('')
  const [selected, setSelected] = useState<Session>()
  const [deleting, setDeleting] = useState<Session>()
  const toast = useToast()

  const patients = useMemo(() => [...new Set((data ?? []).map((s) => s.patient_id))].sort(), [data])
  const games = useMemo(() => [...new Set((data ?? []).map((s) => s.game_name))].sort(), [data])
  const rows = (data ?? []).filter((s) => (!patient || s.patient_id === patient) && (!game || s.game_name === game))

  const remove = async () => {
    if (!deleting) return
    try {
      await api.deleteSession(deleting.session_id)
      toast(`Session #${deleting.session_id} deleted`, 'good')
      setDeleting(undefined)
      reload()
    } catch (e) {
      toast((e as Error).message, 'bad')
    }
  }

  return (
    <>
      <PageHeader title="Sessions" subtitle="Every recorded game session across all patients. Click a row to inspect its attempts." />
      {error && <ErrorBox error={error} onRetry={reload} />}
      {loading && !data && !error && <Loading />}
      {data && (
        <Card
          title={`${rows.length} session${rows.length === 1 ? '' : 's'}`}
          actions={
            <>
              <select value={patient} onChange={(e) => setPatient(e.target.value)} aria-label="Filter by patient">
                <option value="">All patients</option>
                {patients.map((p) => (
                  <option key={p}>{p}</option>
                ))}
              </select>
              <select value={game} onChange={(e) => setGame(e.target.value)} aria-label="Filter by game">
                <option value="">All games</option>
                {games.map((g) => (
                  <option key={g} value={g}>
                    {gameLabel(g)}
                  </option>
                ))}
              </select>
            </>
          }
        >
          {rows.length === 0 ? (
            <Empty title="No sessions found">
              Sessions appear here after a game is played from the <Link to="/games">Game Launcher</Link>.
            </Empty>
          ) : (
            <div className="table-wrap">
              <table className="table table-click">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Date</th>
                    <th>Patient</th>
                    <th>Game</th>
                    <th className="r">Score</th>
                    <th className="r">Attempts</th>
                    <th className="r">Duration</th>
                    <th className="r">Accuracy</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {rows.map((s) => (
                    <tr key={s.session_id} onClick={() => setSelected(s)}>
                      <td>{s.session_id}</td>
                      <td>{dateTime(s.started_at)}</td>
                      <td>
                        <Link to={`/patients/${s.patient_id}`} onClick={(e) => e.stopPropagation()}>
                          {s.patient_id}
                        </Link>
                      </td>
                      <td>{gameLabel(s.game_name)}</td>
                      <td className="r">{s.total_score}</td>
                      <td className="r">{s.attempts ?? '—'}</td>
                      <td className="r">{duration(s.duration_s)}</td>
                      <td className="r">
                        <Badge tone={accuracyTone(s.accuracy)}>{pct(s.accuracy)}</Badge>
                      </td>
                      <td className="r">
                        <button
                          className="icon-btn danger"
                          aria-label={`Delete session ${s.session_id}`}
                          title="Delete session"
                          onClick={(e) => {
                            e.stopPropagation()
                            setDeleting(s)
                          }}
                        >
                          ✕
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}
      {selected && <SessionModal session={selected} onClose={() => setSelected(undefined)} />}
      {deleting && (
        <Modal title={`Delete session #${deleting.session_id}?`} onClose={() => setDeleting(undefined)}>
          <p>
            This permanently deletes the {gameLabel(deleting.game_name)} session for {deleting.patient_id} from {dateTime(deleting.started_at)} and all its attempts.
          </p>
          <div className="form-actions">
            <button className="btn" onClick={() => setDeleting(undefined)}>
              Cancel
            </button>
            <button className="btn btn-danger-solid" onClick={remove}>
              Delete
            </button>
          </div>
        </Modal>
      )}
    </>
  )
}
