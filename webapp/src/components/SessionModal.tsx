import { CartesianGrid, Line, LineChart, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api'
import { dateTime, duration, gameLabel, movement, pct, sig } from '../format'
import { useAsync } from '../hooks'
import type { Session } from '../types'
import { ChartBox, useChartStyle } from './charts'
import { Badge, Empty, ErrorBox, Loading, Modal, Stat, accuracyTone } from './ui'

export function SessionModal({ session, onClose }: { session: Session; onClose: () => void }) {
  const { data, error, loading, reload } = useAsync(() => api.attempts(session.session_id), [session.session_id])
  const chart = useChartStyle()
  const avgRt = data?.length ? data.reduce((a, x) => a + x.reaction_time_ms, 0) / data.length : null
  const hasEmg = data?.some((a) => a.emg_rms > 0 || a.emg_mav > 0)
  const grips = data?.filter((a) => a.effort_ok !== null && a.effort_ok !== undefined) ?? []

  return (
    <Modal title={`Session #${session.session_id} · ${gameLabel(session.game_name)}`} onClose={onClose} wide>
      <p className="muted">
        Patient {session.patient_id} · {dateTime(session.started_at)}
        {session.level ? ` · Level ${session.level}: ${session.level_passed ? 'goal reached' : 'goal not reached'}` : ''}
      </p>
      <div className="stats stats-sm">
        <Stat label="Score" value={session.total_score} />
        <Stat label="Duration" value={duration(session.duration_s)} />
        <Stat label="Accuracy" value={pct(session.accuracy)} />
        <Stat label="Avg reaction" value={avgRt === null ? '—' : `${avgRt.toFixed(0)} ms`} />
        {grips.length > 0 && <Stat label="Strong grips" value={`${grips.filter((a) => a.effort_ok).length} of ${grips.length}`} />}
      </div>
      {error && <ErrorBox error={error} onRetry={reload} />}
      {loading && !data && <Loading />}
      {data && data.length === 0 && <Empty title="No attempts were recorded for this session" />}
      {data && data.length > 0 && (
        <>
          <h3 className="section-title">Reaction time{hasEmg ? ' and EMG activity' : ''} per attempt</h3>
          <ChartBox height={220}>
            <LineChart data={data.map((a, i) => ({ n: i + 1, rt: a.reaction_time_ms, rms: a.emg_rms || null }))}>
              <CartesianGrid {...chart.grid} />
              <XAxis dataKey="n" {...chart.axis} />
              <YAxis yAxisId="rt" unit=" ms" {...chart.axis} width={64} />
              {hasEmg && <YAxis yAxisId="rms" orientation="right" {...chart.axis} width={48} />}
              <Tooltip {...chart.tooltip} labelFormatter={(n) => `Attempt ${n}`} formatter={(v: number) => sig(v)} />
              <Line yAxisId="rt" dataKey="rt" name="Reaction (ms)" stroke={chart.color(0)} strokeWidth={2} dot={{ r: 2 }} />
              {hasEmg && <Line yAxisId="rms" dataKey="rms" name="EMG RMS" stroke={chart.color(2)} strokeWidth={2} dot={{ r: 2 }} connectNulls />}
            </LineChart>
          </ChartBox>
          <div className="table-wrap table-scroll">
            <table className="table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Target</th>
                  <th>Detected</th>
                  <th>Result</th>
                  <th className="r">Reaction</th>
                  <th className="r">EMG RMS</th>
                  <th className="r">EMG MAV</th>
                  <th className="r">Confidence</th>
                  {grips.length > 0 && <th className="r">Grip effort</th>}
                </tr>
              </thead>
              <tbody>
                {data.map((a, i) => (
                  <tr key={a.attempt_id}>
                    <td>{i + 1}</td>
                    <td>{movement(a.target_movement)}</td>
                    <td>{movement(a.detected_movement)}</td>
                    <td>
                      <Badge tone={a.correct ? 'good' : 'bad'}>{a.correct ? 'Correct' : 'Missed'}</Badge>
                    </td>
                    <td className="r">{a.reaction_time_ms} ms</td>
                    <td className="r">{a.emg_rms ? sig(a.emg_rms) : '—'}</td>
                    <td className="r">{a.emg_mav ? sig(a.emg_mav) : '—'}</td>
                    <td className="r">{a.confidence ? <Badge tone={accuracyTone(a.confidence)}>{pct(a.confidence)}</Badge> : '—'}</td>
                    {grips.length > 0 && (
                      <td className="r">
                        {a.effort_ok === null || a.effort_ok === undefined ? (
                          '—'
                        ) : (
                          <Badge tone={a.effort_ok ? 'good' : 'bad'}>
                            {`${(a.emg_activity_pct ?? 0).toFixed(0)}% / ${(a.effort_required_pct ?? 0).toFixed(0)}%`}
                          </Badge>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Modal>
  )
}
