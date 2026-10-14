import { useMemo, useState } from 'react'
import { Bar, BarChart, CartesianGrid, ErrorBar, Legend, Line, LineChart, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api'
import { ChartBox, useChartStyle } from '../components/charts'
import { Badge, Card, Empty, ErrorBox, Loading, PageHeader } from '../components/ui'
import { sig } from '../format'
import { useAsync } from '../hooks'
import type { DatasetFile } from '../types'

const CATEGORY: Record<DatasetFile['category'], { label: string; tone: 'info' | 'good' | 'warn' | 'neutral' }> = {
  normal: { label: 'Healthy · raw', tone: 'info' },
  filtered: { label: 'Healthy · filtered', tone: 'good' },
  patient: { label: 'Patient (simulated)', tone: 'warn' },
  recorded: { label: 'Recorded', tone: 'neutral' },
}

export default function Datasets() {
  const list = useAsync(() => api.datasets(), [])
  const [tab, setTab] = useState<'explore' | 'compare'>('explore')
  const [file, setFile] = useState<string>()
  const current = file ?? list.data?.find((f) => f.rows > 0)?.file

  return (
    <>
      <PageHeader
        title="EMG Datasets"
        subtitle="Browse the healthy-volunteer and patient EMG datasets, view signals and compute activity features (RMS, MAV, VAR, peak, waveform length)."
        actions={
          <div className="segmented">
            <button className={tab === 'explore' ? 'active' : ''} onClick={() => setTab('explore')}>
              Explore file
            </button>
            <button className={tab === 'compare' ? 'active' : ''} onClick={() => setTab('compare')}>
              Compare groups
            </button>
          </div>
        }
      />
      {list.error && <ErrorBox error={list.error} onRetry={list.reload} />}
      {list.loading && !list.data && <Loading />}
      {list.data && tab === 'explore' && (
        <div className="split">
          <FileList files={list.data} current={current} onSelect={setFile} />
          <div className="split-main">{current ? <FileView key={current} file={list.data.find((f) => f.file === current)!} /> : <Empty title="No datasets found" />}</div>
        </div>
      )}
      {list.data && tab === 'compare' && <Compare />}
    </>
  )
}

function FileList({ files, current, onSelect }: { files: DatasetFile[]; current?: string; onSelect: (f: string) => void }) {
  const [filter, setFilter] = useState('')
  const groups = useMemo(() => {
    const m = new Map<string, DatasetFile[]>()
    files
      .filter((f) => !filter || f.file.toLowerCase().includes(filter.toLowerCase()))
      .forEach((f) => m.set(f.folder, [...(m.get(f.folder) ?? []), f]))
    return [...m.entries()]
  }, [files, filter])
  return (
    <Card className="file-list" title={`${files.length} files`}>
      <input className="search full" placeholder="Filter files…" value={filter} onChange={(e) => setFilter(e.target.value)} />
      <div className="file-scroll">
        {groups.map(([folder, fs]) => (
          <div key={folder} className="file-group">
            <div className="file-group-title">{folder.replace(/^Datasets\//, '').replace(/^data\//, '')}</div>
            {fs.map((f) => (
              <button key={f.file} className={`file-item ${f.file === current ? 'active' : ''}`} onClick={() => onSelect(f.file)}>
                <span>{f.name}</span>
                <small className="muted">{f.rows ? `${f.rows.toLocaleString()} rows` : 'empty'}</small>
              </button>
            ))}
          </div>
        ))}
      </div>
    </Card>
  )
}

function FileView({ file }: { file: DatasetFile }) {
  const [win, setWin] = useState(200)
  const signal = useAsync(() => api.signal(file.file), [file.file])
  const feats = useAsync(() => api.features(file.file, win, Math.max(1, Math.round(win / 2))), [file.file, win])
  const chart = useChartStyle()
  const cols = signal.data?.columns ?? []
  const [hidden, setHidden] = useState<Set<string>>(new Set())
  const visible = cols.filter((c) => !hidden.has(c))
  const toggle = (c: string) => setHidden((h) => (h.has(c) ? new Set([...h].filter((x) => x !== c)) : new Set([...h, c])))

  const signalData = useMemo(() => {
    const d = signal.data
    if (!d) return []
    return d.index.map((x, i) => {
      const row: Record<string, number | string | null> = { x }
      d.columns.forEach((c) => (row[c] = d.series[c][i]))
      if (d.labels) row.label = d.labels[i]
      return row
    })
  }, [signal.data])

  const rmsData = useMemo(() => {
    const s = feats.data?.rms_series ?? {}
    const keys = Object.keys(s)
    const len = Math.max(0, ...keys.map((k) => s[k].length))
    return Array.from({ length: len }, (_, i) => {
      const row: Record<string, number> = { n: i }
      keys.forEach((k) => (row[k] = s[k][i]))
      return row
    })
  }, [feats.data])

  return (
    <>
      <Card
        title={file.name}
        actions={
          <>
            <Badge tone={CATEGORY[file.category].tone}>{CATEGORY[file.category].label}</Badge>
            <span className="muted small">
              {file.rows.toLocaleString()} rows · {file.size_kb} KB
            </span>
          </>
        }
      >
        {signal.error && <ErrorBox error={signal.error} onRetry={signal.reload} />}
        {signal.loading && !signal.data && <Loading label="Loading signal…" />}
        {signal.data && signal.data.rows === 0 && <Empty title="This file has no samples yet">Record data with the EMG or fused logger to populate it.</Empty>}
        {signal.data && signal.data.rows > 0 && (
          <>
            <div className="chips">
              {cols.map((c, i) => (
                <button key={c} className={`chip ${hidden.has(c) ? 'off' : ''}`} onClick={() => toggle(c)} style={{ ['--chip' as string]: chart.color(i) }}>
                  <span className="chip-dot" /> {c}
                </button>
              ))}
            </div>
            <ChartBox height={320}>
              <LineChart data={signalData}>
                <CartesianGrid {...chart.grid} />
                <XAxis dataKey="x" {...chart.axis} minTickGap={40} />
                <YAxis {...chart.axis} width={56} tickFormatter={(v) => sig(v)} />
                <Tooltip {...chart.tooltip} formatter={(v: number) => sig(v)} labelFormatter={(x, pl) => `Sample ${x}${pl?.[0]?.payload?.label ? ` · ${pl[0].payload.label}` : ''}`} />
                {visible.map((c) => (
                  <Line key={c} dataKey={c} stroke={chart.color(cols.indexOf(c))} dot={false} strokeWidth={1.25} isAnimationActive={false} />
                ))}
              </LineChart>
            </ChartBox>
            <p className="caption">
              Showing {signalData.length.toLocaleString()} of {signal.data.rows.toLocaleString()} samples (peak-preserving downsampling).
            </p>
          </>
        )}
      </Card>

      {signal.data && signal.data.rows > 0 && (
        <Card
          title="Activity features"
          actions={
            <label className="inline">
              Window
              <select value={win} onChange={(e) => setWin(Number(e.target.value))}>
                {[50, 100, 200, 500, 1000].map((w) => (
                  <option key={w} value={w}>
                    {w} samples
                  </option>
                ))}
              </select>
            </label>
          }
        >
          {feats.error && <ErrorBox error={feats.error} onRetry={feats.reload} />}
          {feats.loading && !feats.data && <Loading label="Computing features…" />}
          {feats.data && (
            <>
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Movement</th>
                      <th className="r">RMS</th>
                      <th className="r">MAV</th>
                      <th className="r">VAR</th>
                      <th className="r">STD</th>
                      <th className="r">Peak</th>
                      <th className="r">WL / sample</th>
                      <th className="r">Samples</th>
                    </tr>
                  </thead>
                  <tbody>
                    {feats.data.features.map((f) => (
                      <tr key={f.movement}>
                        <td>{f.movement}</td>
                        <td className="r">{sig(f.RMS)}</td>
                        <td className="r">{sig(f.MAV)}</td>
                        <td className="r">{sig(f.VAR)}</td>
                        <td className="r">{sig(f.STD)}</td>
                        <td className="r">{sig(f.PEAK)}</td>
                        <td className="r">{sig(f.WL)}</td>
                        <td className="r">{f.samples?.toLocaleString() ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <h3 className="section-title">Windowed RMS envelope</h3>
              <ChartBox height={240}>
                <LineChart data={rmsData}>
                  <CartesianGrid {...chart.grid} />
                  <XAxis dataKey="n" {...chart.axis} minTickGap={40} />
                  <YAxis {...chart.axis} width={56} tickFormatter={(v) => sig(v)} />
                  <Tooltip {...chart.tooltip} formatter={(v: number) => sig(v)} labelFormatter={(n) => `Window ${n}`} />
                  {Object.keys(feats.data.rms_series)
                    .filter((c) => !hidden.has(c))
                    .map((c) => (
                      <Line key={c} dataKey={c} stroke={chart.color(Math.max(0, cols.indexOf(c)))} dot={false} strokeWidth={1.5} isAnimationActive={false} />
                    ))}
                </LineChart>
              </ChartBox>
            </>
          )}
        </Card>
      )}
    </>
  )
}

function Compare() {
  const { data, error, loading, reload } = useAsync(() => api.compare(), [])
  const [metric, setMetric] = useState<'RMS' | 'MAV'>('RMS')
  const [relative, setRelative] = useState(true)
  const chart = useChartStyle()
  const cats = Object.keys(data?.categories ?? {}) as DatasetFile['category'][]
  const rows = useMemo(() => {
    if (!data) return []
    const movements = [...new Set(cats.flatMap((c) => data.categories[c].map((m) => m.movement)))]
    // Groups use different units, so optionally scale each group to % of its own largest movement.
    const scale = Object.fromEntries(cats.map((c) => [c, relative ? 100 / Math.max(...data.categories[c].map((x) => x[metric])) : 1]))
    return movements.map((m) => {
      const row: Record<string, string | number | undefined> = { movement: m }
      cats.forEach((c) => {
        const v = data.categories[c].find((x) => x.movement === m)
        row[c] = v ? v[metric] * scale[c] : undefined
        row[`${c}_err`] = metric === 'RMS' && v ? v.RMS_std * scale[c] : undefined
      })
      return row
    })
  }, [data, metric, cats, relative])

  return (
    <Card
      title={`Mean ${metric} per movement by group`}
      actions={
        <>
        <label className="inline">
          <input type="checkbox" checked={relative} onChange={(e) => setRelative(e.target.checked)} /> Normalize per group
        </label>
        <div className="segmented">
          {(['RMS', 'MAV'] as const).map((m) => (
            <button key={m} className={metric === m ? 'active' : ''} onClick={() => setMetric(m)}>
              {m}
            </button>
          ))}
        </div>
        </>
      }
    >
      {error && <ErrorBox error={error} onRetry={reload} />}
      {loading && !data && <Loading label="Computing features across all files…" />}
      {data && (
        <>
          <ChartBox height={360}>
            <BarChart data={rows}>
              <CartesianGrid {...chart.grid} />
              <XAxis dataKey="movement" {...chart.axis} />
              <YAxis {...chart.axis} width={56} unit={relative ? '%' : undefined} tickFormatter={(v) => (relative ? v.toFixed(0) : sig(v))} />
              <Tooltip {...chart.tooltip} formatter={(v: number) => (relative ? `${v.toFixed(0)}%` : sig(v))} />
              <Legend {...chart.legend} />
              {cats.map((c, i) => (
                <Bar key={c} dataKey={c} name={`${CATEGORY[c].label} (${data.files[c]} files)`} fill={chart.color(i)} radius={[4, 4, 0, 0]} maxBarSize={28}>
                  {metric === 'RMS' && <ErrorBar dataKey={`${c}_err`} stroke={chart.palette.axis} width={4} />}
                </Bar>
              ))}
            </BarChart>
          </ChartBox>
          <p className="caption">
            Averaged over every file in each group; error bars show the standard deviation of per-file RMS. Units differ between groups (healthy data in ADC-derived units, simulated
            patient data in mV), so by default each group is shown as a percentage of its most active movement — compare activity patterns, not absolute magnitudes.
            Values are electrical activity indicators, not clinical muscle-strength scores.
          </p>
        </>
      )}
    </Card>
  )
}
