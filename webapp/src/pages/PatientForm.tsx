import { useState, type FormEvent } from 'react'
import { api } from '../api'
import type { Patient } from '../types'

const EMPTY: Patient = { patient_id: '', age: null, affected_side: null, stroke_date: null, notes: null }
export const PATIENT_RE = /^P[A-Za-z0-9_-]{1,20}$/

export function PatientForm({ initial, onSaved, onCancel }: { initial?: Patient; onSaved: (p: Patient) => void; onCancel: () => void }) {
  const editing = !!initial
  const [p, setP] = useState<Patient>(initial ?? EMPTY)
  const [error, setError] = useState<string>()
  const [busy, setBusy] = useState(false)
  const set = <K extends keyof Patient>(k: K, v: Patient[K]) => setP((x) => ({ ...x, [k]: v }))

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!PATIENT_RE.test(p.patient_id)) {
      setError('Patient code must start with P and contain only letters, numbers, _ or - (2–21 characters).')
      return
    }
    setBusy(true)
    setError(undefined)
    try {
      const clean: Patient = {
        ...p,
        affected_side: p.affected_side || null,
        stroke_date: p.stroke_date || null,
        notes: p.notes?.trim() || null,
      }
      onSaved(editing ? await api.updatePatient(clean) : await api.createPatient(clean))
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="form" onSubmit={submit}>
      <label>
        Patient code
        <input value={p.patient_id} disabled={editing} onChange={(e) => set('patient_id', e.target.value.trim())} placeholder="P01" autoFocus={!editing} required />
        <small className="muted">Coded identifier only (e.g. P01) — never store names or other identifying details.</small>
      </label>
      <div className="form-row">
        <label>
          Age
          <input type="number" min={0} max={120} value={p.age ?? ''} onChange={(e) => set('age', e.target.value === '' ? null : Number(e.target.value))} />
        </label>
        <label>
          Affected side
          <select value={p.affected_side ?? ''} onChange={(e) => set('affected_side', e.target.value || null)}>
            <option value="">Not specified</option>
            <option value="Left">Left</option>
            <option value="Right">Right</option>
            <option value="Both">Both</option>
          </select>
        </label>
        <label>
          Stroke date
          <input type="date" value={p.stroke_date ?? ''} onChange={(e) => set('stroke_date', e.target.value || null)} />
        </label>
      </div>
      <label>
        Clinical notes
        <textarea rows={4} value={p.notes ?? ''} onChange={(e) => set('notes', e.target.value)} placeholder="Therapy goals, observations…" />
      </label>
      {error && <div className="error-box">{error}</div>}
      <div className="form-actions">
        <button type="button" className="btn" onClick={onCancel}>
          Cancel
        </button>
        <button className="btn btn-primary" disabled={busy}>
          {busy ? 'Saving…' : editing ? 'Save changes' : 'Add patient'}
        </button>
      </div>
    </form>
  )
}
