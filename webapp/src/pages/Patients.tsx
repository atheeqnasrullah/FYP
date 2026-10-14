import { useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { Badge, Card, Empty, ErrorBox, Loading, Modal, PageHeader, accuracyTone, useToast } from '../components/ui'
import { pct, relativeDay } from '../format'
import { Sparkline, TrendChip } from '../components/Trend'
import { useAsync } from '../hooks'
import { PatientForm } from './PatientForm'

export default function Patients() {
  const { data, error, loading, reload } = useAsync(() => api.patients(), [])
  const [params, setParams] = useSearchParams()
  const [adding, setAddingState] = useState(params.get('add') === '1')
  const setAdding = (v: boolean) => {
    setAddingState(v)
    if (!v && params.get('add')) setParams({}, { replace: true })
  }
  const [query, setQuery] = useState('')
  const toast = useToast()
  const navigate = useNavigate()

  const rows = useMemo(() => {
    const ql = query.toLowerCase()
    return (data ?? []).filter((p) => !ql || p.patient_id.toLowerCase().includes(ql) || (p.notes ?? '').toLowerCase().includes(ql))
  }, [data, query])

  return (
    <>
      <PageHeader
        title="Patients"
        subtitle="Coded patient records and their rehabilitation progress."
        actions={
          <button className="btn btn-primary" onClick={() => setAdding(true)}>
            + Add patient
          </button>
        }
      />
      {error && <ErrorBox error={error} onRetry={reload} />}
      {loading && !data && !error && <Loading />}
      {data && (
        <Card
          title={`${data.length} patient${data.length === 1 ? '' : 's'}`}
          actions={<input className="search" placeholder="Search code or notes…" value={query} onChange={(e) => setQuery(e.target.value)} />}
        >
          {data.length === 0 ? (
            <Empty title="No patients yet">Add a patient to start tracking rehabilitation sessions. Games also create a record automatically on first save.</Empty>
          ) : rows.length === 0 ? (
            <Empty title="No matches" />
          ) : (
            <div className="table-wrap">
              <table className="table table-click">
                <thead>
                  <tr>
                    <th>Code</th>
                    <th>Age</th>
                    <th>Affected side</th>
                    <th className="r">Sessions</th>
                    <th className="r">Avg accuracy</th>
                    <th>Recent accuracy</th>
                    <th>Trend</th>
                    <th>Last session</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((p) => (
                    <tr key={p.patient_id} onClick={() => navigate(`/patients/${p.patient_id}`)}>
                      <td>
                        <Link to={`/patients/${p.patient_id}`} onClick={(e) => e.stopPropagation()}>
                          <strong>{p.patient_id}</strong>
                        </Link>
                      </td>
                      <td>{p.age ?? '—'}</td>
                      <td>{p.affected_side ?? '—'}</td>
                      <td className="r">{p.sessions}</td>
                      <td className="r">{p.sessions ? <Badge tone={accuracyTone(p.avg_accuracy)}>{pct(p.avg_accuracy)}</Badge> : '—'}</td>
                      <td>
                        <Sparkline values={p.recent_accuracy} />
                      </td>
                      <td>
                        <TrendChip trend={p.trend} />
                      </td>
                      <td>{relativeDay(p.last_session)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}
      {adding && (
        <Modal title="Add patient" onClose={() => setAdding(false)}>
          <PatientForm
            onCancel={() => setAdding(false)}
            onSaved={(p) => {
              setAdding(false)
              toast(`Patient ${p.patient_id} added`, 'good')
              reload()
            }}
          />
        </Modal>
      )}
    </>
  )
}
