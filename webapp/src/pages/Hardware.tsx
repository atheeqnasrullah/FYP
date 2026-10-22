import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { Badge, Card, ErrorBox, Loading, PageHeader, useToast } from '../components/ui'
import { SignalCanvas } from '../components/SignalCanvas'
import { useAsync } from '../hooks'
import { emgBadge, emgTone } from '../format'
import type { CameraCheck, EmgReport, HardwarePorts } from '../types'

const WINDOW_S = 5
const CAMERA_INDEXES = [0, 1, 2, 3]

type StreamState = 'idle' | 'connecting' | 'live' | 'error'

/** Live EMG over server-sent events: samples go into a ref buffer, verdicts into state once a second. */
function useEmgStream() {
  const [state, setState] = useState<StreamState>('idle')
  const [report, setReport] = useState<EmgReport>()
  const [error, setError] = useState<string>()
  const [capacity, setCapacity] = useState(1000)
  const buffer = useRef<number[]>([])
  const source = useRef<EventSource | null>(null)

  const stop = useCallback(() => {
    source.current?.close()
    source.current = null
    setState((s) => (s === 'error' ? s : 'idle'))
  }, [])

  const start = useCallback((port: string) => {
    source.current?.close()
    buffer.current = []
    setReport(undefined)
    setError(undefined)
    setState('connecting')
    const es = new EventSource(api.emgStreamUrl(port))
    source.current = es
    let max = 1000
    const data = (e: Event) => JSON.parse((e as MessageEvent).data)
    es.addEventListener('ready', (e) => {
      max = Math.round(data(e).chart_hz * WINDOW_S)
      setCapacity(max)
      setState('live')
    })
    es.onmessage = (e) => {
      const b = buffer.current
      b.push(...(JSON.parse(e.data).samples as number[]))
      if (b.length > max) b.splice(0, b.length - max)
    }
    es.addEventListener('status', (e) => setReport(data(e)))
    es.addEventListener('failure', (e) => {
      setError(data(e).message)
      setState('error')
      es.close()
    })
    es.addEventListener('end', () => {
      es.close()
      setState('idle')
    })
    es.onerror = () => {
      if (source.current !== es || es.readyState === EventSource.CLOSED) return
      es.close()
      source.current = null
      setState('error')
      setError((prev) => prev ?? 'The live signal stopped. The API may have restarted, or a game is using the sensor.')
    }
  }, [])

  useEffect(() => () => source.current?.close(), [])
  return { state, report, error, capacity, buffer, start, stop }
}

export default function Hardware() {
  const ports = useAsync(() => api.hardwarePorts(), [], 4000)
  const toast = useToast()
  const p = ports.data

  return (
    <>
      <PageHeader
        title="Hardware"
        subtitle="Connect the ESP32 EMG sensor and the webcam, and check that both work before a session. Previews here close automatically when a game starts."
        actions={
          <button className="btn" onClick={ports.reload}>
            Refresh
          </button>
        }
      />
      {ports.error && <ErrorBox error={ports.error} onRetry={ports.reload} />}
      {!p && !ports.error && <Loading />}
      {p && (
        <div className="grid-2 hw-grid">
          <EmgCard ports={p} onSaved={ports.reload} toast={toast} />
          <CameraCard ports={p} onSaved={ports.reload} toast={toast} />
        </div>
      )}
      <Card title="If something is not working">
        <ul className="hw-tips">
          <li>
            <strong>ESP32 not detected:</strong> use a data USB cable (some are charge-only) and install the CP210x or CH340 driver. The board should appear as a COM port.
          </li>
          <li>
            <strong>Port busy:</strong> close the Arduino IDE Serial Monitor or Serial Plotter, and stop any EMG logger, then test again.
          </li>
          <li>
            <strong>No data:</strong> flash <code>firmware/emg_acquisition</code> and press EN/RESET on the board. The baud rate must be 921600.
          </li>
          <li>
            <strong>Flat or stuck signal:</strong> check the sensor's power (3.3–5 V), ground and SIG wire on GPIO34, and the electrode contact.
          </li>
          <li>
            <strong>No webcam:</strong> close Zoom, Teams or the Camera app, allow camera access in Windows privacy settings, or try another camera number.
          </li>
        </ul>
      </Card>
    </>
  )
}

interface CardProps {
  ports: HardwarePorts
  onSaved: () => void
  toast: ReturnType<typeof useToast>
}

function EmgCard({ ports, onSaved, toast }: CardProps) {
  const [port, setPort] = useState(ports.configured_present || !ports.suggested_port ? ports.configured_port : ports.suggested_port)
  const [check, setCheck] = useState<EmgReport>()
  const [checkError, setCheckError] = useState<string>()
  const [testing, setTesting] = useState(false)
  const stream = useEmgStream()
  const stopStream = stream.stop
  const testBuffer = useRef<number[]>([])
  const busy = ports.game_using_emg

  useEffect(() => {
    if (busy) stopStream()
  }, [busy, stopStream])

  // Board plugged in on a different port while the page is open: switch to it.
  const selectedPresent = ports.ports.some((x) => x.device === port)
  useEffect(() => {
    if (!selectedPresent && ports.suggested_port) setPort(ports.suggested_port)
  }, [selectedPresent, ports.suggested_port])

  const options = ports.ports.some((x) => x.device === port) ? ports.ports : [...ports.ports, { device: port, description: 'not connected', manufacturer: null, chip: null, likely_esp32: false }]
  const info = ports.ports.find((x) => x.device === port)
  const live = stream.state === 'live' || stream.state === 'connecting'
  const report = live || stream.report ? stream.report : check
  const error = stream.error ?? checkError

  const test = async () => {
    stream.stop()
    setTesting(true)
    setCheckError(undefined)
    try {
      const r = await api.emgCheck(port)
      testBuffer.current = r.signal ?? []
      setCheck(r)
    } catch (e) {
      setCheck(undefined)
      setCheckError((e as Error).message)
    } finally {
      setTesting(false)
    }
  }
  const save = async () => {
    try {
      await api.saveHardware({ serial_port: port })
      toast(`Games will use the EMG sensor on ${port}`, 'good')
      onSaved()
    } catch (e) {
      toast((e as Error).message, 'bad')
    }
  }

  let presence: [string, 'good' | 'warn' | 'bad' | 'info' | 'neutral'] = info ? ['Plugged in', 'info'] : ['Not detected', 'bad']
  if (busy) presence = ['In use by the game', 'info']
  else if (report) presence = [emgBadge(report), emgTone(report)]
  else if (error) presence = ['Problem', 'bad']

  return (
    <Card title="EMG sensor (ESP32)" actions={<Badge tone={presence[1]}>{presence[0]}</Badge>}>
      <div className="form">
        <label>
          Serial port
          <div className="input-row">
            <select value={port} onChange={(e) => setPort(e.target.value)} disabled={live}>
              {options.map((o) => (
                <option key={o.device} value={o.device}>
                  {o.device} · {o.likely_esp32 ? `${o.chip} (ESP32 board)` : o.description}
                </option>
              ))}
            </select>
            {port !== ports.configured_port && (
              <button className="btn" onClick={save}>
                Use for games
              </button>
            )}
          </div>
          <small className="muted">
            {ports.ports.length === 0
              ? 'No serial ports found. Plug in the ESP32 with a data USB cable.'
              : port === ports.configured_port
                ? `Games use this port at ${ports.baud_rate} baud, ${ports.fs} Hz.`
                : `Games currently use ${ports.configured_port}.`}
            {!ports.configured_present && ports.suggested_port && port !== ports.suggested_port && ` An ESP32 board was found on ${ports.suggested_port}.`}
          </small>
        </label>
        <div className="form-actions start">
          {live ? (
            <button className="btn btn-danger-solid" onClick={stream.stop}>
              Stop live signal
            </button>
          ) : (
            <button className="btn btn-primary" onClick={() => stream.start(port)} disabled={busy || !port}>
              Start live signal
            </button>
          )}
          <button className="btn" onClick={test} disabled={busy || testing || !port}>
            {testing ? 'Testing…' : 'Quick test'}
          </button>
          {stream.state === 'connecting' && <span className="muted small">Connecting…</span>}
          {stream.state === 'live' && (
            <span className="live-label small">
              <span className="live-dot" /> Live · last {WINDOW_S} s
            </span>
          )}
        </div>
        {busy && <p className="muted small">A Webcam + EMG game is running and using the sensor. Stop it to test here.</p>}
        {error && <div className="error-box">{error}</div>}
        {live || stream.report ? (
          <SignalCanvas buffer={stream.buffer} capacity={stream.capacity} label="Live EMG signal" />
        ) : check?.signal?.length ? (
          <SignalCanvas buffer={testBuffer} capacity={check.signal.length} label="EMG signal from the quick test" />
        ) : null}
        {report && <EmgReadout r={report} />}
      </div>
    </Card>
  )
}

function EmgReadout({ r }: { r: EmgReport }) {
  return (
    <>
      <p className={`hw-verdict hw-${emgTone(r)}`}>{r.message}</p>
      {r.warnings.map((w) => (
        <p key={w} className="hw-verdict hw-warn">
          {w}
        </p>
      ))}
      <dl className="kv">
        <dt>Sample rate</dt>
        <dd>
          {r.rate_hz ? `${r.rate_hz} Hz` : '—'} <span className="muted">(expected {r.expected_hz} Hz)</span>
        </dd>
        <dt>Signal range</dt>
        <dd>{r.min === null ? '—' : `${r.min} – ${r.max} (mean ${r.mean})`}</dd>
        <dt>Received</dt>
        <dd>
          {r.samples} samples, {(r.bytes / 1024).toFixed(1)} KB{r.bad_lines ? `, ${r.bad_lines} malformed` : ''}
        </dd>
        {r.messages.length > 0 && (
          <>
            <dt>Board says</dt>
            <dd>{r.messages[r.messages.length - 1]}</dd>
          </>
        )}
        {r.bad_examples.length > 0 && r.status !== 'streaming' && (
          <>
            <dt>Received text</dt>
            <dd>
              <code>{r.bad_examples[0]}</code>
            </dd>
          </>
        )}
      </dl>
    </>
  )
}

function CameraCard({ ports, onSaved, toast }: CardProps) {
  const [index, setIndex] = useState(ports.camera_index)
  const [streamUrl, setStreamUrl] = useState<string>()
  const [shown, setShown] = useState(false)
  const [snapshot, setSnapshot] = useState<CameraCheck>()
  const [error, setError] = useState<string>()
  const [testing, setTesting] = useState(false)
  const busy = ports.game_using_camera

  useEffect(() => {
    if (busy) setStreamUrl(undefined)
  }, [busy])

  const diagnose = async (i: number) => {
    setTesting(true)
    setError(undefined)
    try {
      setSnapshot(await api.cameraCheck(i))
    } catch (e) {
      setSnapshot(undefined)
      setError((e as Error).message)
    } finally {
      setTesting(false)
    }
  }
  const startPreview = () => {
    setError(undefined)
    setSnapshot(undefined)
    setShown(false)
    setStreamUrl(api.cameraStreamUrl(index))
  }
  const stopPreview = () => {
    setStreamUrl(undefined)
    setShown(false)
  }
  const choose = (i: number) => {
    stopPreview()
    setSnapshot(undefined)
    setError(undefined)
    setIndex(i)
  }
  const save = async () => {
    try {
      await api.saveHardware({ camera_index: index })
      toast(`Games will use camera ${index}`, 'good')
      onSaved()
    } catch (e) {
      toast((e as Error).message, 'bad')
    }
  }

  let status: [string, 'good' | 'warn' | 'bad' | 'info' | 'neutral'] = ['Not tested', 'neutral']
  if (busy) status = ['In use by the game', 'info']
  else if (error) status = ['Not working', 'bad']
  else if (streamUrl && shown) status = ['Live', 'good']
  else if (streamUrl) status = ['Connecting…', 'info']
  else if (snapshot) status = snapshot.dark ? ['Picture is dark', 'warn'] : ['Working', 'good']

  return (
    <Card title="Webcam" actions={<Badge tone={status[1]}>{status[0]}</Badge>}>
      <div className="form">
        <label>
          Camera
          <div className="input-row">
            <div className="segmented">
              {CAMERA_INDEXES.map((i) => (
                <button key={i} type="button" className={i === index ? 'active' : ''} onClick={() => choose(i)}>
                  Camera {i}
                </button>
              ))}
            </div>
            {index !== ports.camera_index && (
              <button className="btn" onClick={save}>
                Use for games
              </button>
            )}
          </div>
          <small className="muted">{index === ports.camera_index ? 'Games use this camera. Camera 0 is usually the built-in webcam.' : `Games currently use camera ${ports.camera_index}.`}</small>
        </label>
        <div className="form-actions start">
          {streamUrl ? (
            <button className="btn btn-danger-solid" onClick={stopPreview}>
              Stop preview
            </button>
          ) : (
            <button className="btn btn-primary" onClick={startPreview} disabled={busy}>
              Start preview
            </button>
          )}
          <button
            className="btn"
            onClick={() => {
              stopPreview()
              diagnose(index)
            }}
            disabled={busy || testing}
          >
            {testing ? 'Testing…' : 'Take snapshot'}
          </button>
        </div>
        {busy && <p className="muted small">A game is using the webcam. Stop it to preview here.</p>}
        {error && <div className="error-box">{error}</div>}
        <div className="cam-view">
          {streamUrl ? (
            <img
              src={streamUrl}
              alt={`Live view from camera ${index}`}
              onLoad={() => setShown(true)}
              onError={() => {
                setStreamUrl(undefined)
                diagnose(index)
              }}
            />
          ) : snapshot ? (
            <img src={snapshot.image} alt={`Snapshot from camera ${index}`} />
          ) : (
            <span className="muted">{testing ? 'Opening the camera…' : 'No picture yet'}</span>
          )}
        </div>
        {snapshot && (
          <dl className="kv">
            <dt>Resolution</dt>
            <dd>
              {snapshot.width} × {snapshot.height}
            </dd>
            <dt>Driver</dt>
            <dd>{snapshot.backend}</dd>
            {snapshot.dark && (
              <>
                <dt>Note</dt>
                <dd>The picture is very dark. Check the lighting and that the lens is not covered.</dd>
              </>
            )}
          </dl>
        )}
      </div>
    </Card>
  )
}
