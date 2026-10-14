import { useEffect, useState } from 'react'
import { api, defaultApiUrl, getApiUrl, setApiUrl } from '../api'
import { Badge, Card, ErrorBox, Loading, PageHeader, useToast } from '../components/ui'
import { useAsync } from '../hooks'
import { useTheme } from '../theme'

export default function Settings() {
  const { data, error, loading, reload } = useAsync(() => api.settings(), [])
  const [raw, setRaw] = useState('')
  const [saving, setSaving] = useState(false)
  const [apiUrl, setApiUrlState] = useState(getApiUrl())
  const { mode, setMode } = useTheme()
  const toast = useToast()

  useEffect(() => {
    if (data) setRaw(data.raw)
  }, [data])

  const save = async () => {
    setSaving(true)
    try {
      const r = await api.saveSettings(raw)
      setRaw(r.raw)
      toast('Settings saved to config/settings.yaml', 'good')
      reload()
    } catch (e) {
      toast((e as Error).message, 'bad')
    } finally {
      setSaving(false)
    }
  }

  const applyApi = () => {
    setApiUrl(apiUrl === defaultApiUrl() ? null : apiUrl)
    toast('API URL updated', 'good')
    window.location.reload()
  }

  const dirty = data && raw !== data.raw
  const s = data?.settings ?? {}

  return (
    <>
      <PageHeader title="Settings" subtitle="Web app preferences and the system configuration used by the games, sensors and vision pipeline." />
      <div className="grid-2">
        <Card title="Web app">
          <div className="form">
            <label>
              API URL
              <div className="input-row">
                <input value={apiUrl} onChange={(e) => setApiUrlState(e.target.value)} />
                <button className="btn" onClick={applyApi}>
                  Apply
                </button>
              </div>
              <small className="muted">Default: {defaultApiUrl()}</small>
            </label>
            <label>
              Theme
              <div className="segmented">
                {(['system', 'light', 'dark'] as const).map((m) => (
                  <button key={m} type="button" className={mode === m ? 'active' : ''} onClick={() => setMode(m)}>
                    {m[0].toUpperCase() + m.slice(1)}
                  </button>
                ))}
              </div>
            </label>
          </div>
        </Card>
        <Card title="Hardware summary">
          {data ? (
            <dl className="kv">
              <dt>Serial port</dt>
              <dd>{String(s.serial_port ?? '—')}</dd>
              <dt>Baud rate</dt>
              <dd>{String(s.baud_rate ?? '—')}</dd>
              <dt>Sample rate</dt>
              <dd>{s.fs ? `${s.fs} Hz` : '—'}</dd>
              <dt>Signal type</dt>
              <dd>{String(s.signal_type ?? '—')}</dd>
              <dt>Window / step</dt>
              <dd>
                {String(s.window_ms ?? '—')} ms / {String(s.step_ms ?? '—')} ms
              </dd>
              <dt>Camera index</dt>
              <dd>{String(s.camera_index ?? '—')}</dd>
              <dt>Movement labels</dt>
              <dd className="chips">
                {data.labels.map((l) => (
                  <Badge key={l}>{l}</Badge>
                ))}
              </dd>
            </dl>
          ) : (
            <Loading />
          )}
        </Card>
      </div>
      <Card
        title="config/settings.yaml"
        actions={
          <>
            {dirty && <Badge tone="warn">Unsaved changes</Badge>}
            <button className="btn btn-sm" onClick={() => data && setRaw(data.raw)} disabled={!dirty}>
              Revert
            </button>
            <button className="btn btn-sm btn-primary" onClick={save} disabled={!dirty || saving}>
              {saving ? 'Saving…' : 'Save'}
            </button>
          </>
        }
      >
        {error && <ErrorBox error={error} onRetry={reload} />}
        {loading && !data && <Loading />}
        {data && <textarea className="code-editor" spellCheck={false} value={raw} onChange={(e) => setRaw(e.target.value)} rows={Math.max(12, raw.split('\n').length + 1)} />}
        <p className="caption">Changes apply the next time a game or logger starts. The file is validated as YAML before saving.</p>
      </Card>
    </>
  )
}
