import type {
  Attempt, DatasetCompare, DatasetFeatures, DatasetFile, DatasetSignal, GameStatus, GamesInfo,
  Overview, Patient, PatientSummary, Progress, Session, SettingsResponse,
} from './types'

const STORAGE_KEY = 'rehabhub.apiUrl'

/** Default API base: Vite dev proxy in development, same origin when served by FastAPI at /ui. */
export function defaultApiUrl(): string {
  if (import.meta.env.VITE_API_URL) return import.meta.env.VITE_API_URL as string
  return import.meta.env.DEV ? '/api' : window.location.origin
}

export function getApiUrl(): string {
  try {
    return localStorage.getItem(STORAGE_KEY) || defaultApiUrl()
  } catch {
    return defaultApiUrl()
  }
}

export function setApiUrl(url: string | null) {
  try {
    if (url) localStorage.setItem(STORAGE_KEY, url.replace(/\/+$/, ''))
    else localStorage.removeItem(STORAGE_KEY)
  } catch {
    /* storage unavailable */
  }
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(getApiUrl() + path, {
      ...init,
      headers: init?.body ? { 'Content-Type': 'application/json', ...init?.headers } : init?.headers,
    })
  } catch {
    throw new ApiError(0, `Cannot reach the API at ${getApiUrl()}. Start it with: uvicorn backend.app:app --reload`)
  }
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, detail || `Request failed (${res.status})`)
  }
  return res.json() as Promise<T>
}

const json = (method: string, body?: unknown): RequestInit => ({ method, body: body === undefined ? undefined : JSON.stringify(body) })
const q = (params: Record<string, string | number | undefined>) => {
  const s = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => v !== undefined && v !== '' && s.set(k, String(v)))
  const str = s.toString()
  return str ? `?${str}` : ''
}

export const api = {
  health: () => request<{ status: string }>('/health'),
  overview: () => request<Overview>('/overview'),

  patients: () => request<PatientSummary[]>('/patients/summary'),
  patient: (pid: string) => request<Patient>(`/patients/${encodeURIComponent(pid)}`),
  createPatient: (p: Patient) => request<Patient>('/patients', json('POST', p)),
  updatePatient: (p: Patient) => request<Patient>(`/patients/${encodeURIComponent(p.patient_id)}`, json('PUT', p)),
  deletePatient: (pid: string) => request(`/patients/${encodeURIComponent(pid)}`, json('DELETE')),
  progress: (pid: string) => request<Progress>(`/patients/${encodeURIComponent(pid)}/progress`),
  exportUrl: (pid: string) => `${getApiUrl()}/patients/${encodeURIComponent(pid)}/export.csv`,

  sessions: (params: { patient_id?: string; game_name?: string } = {}) => request<Session[]>(`/sessions${q(params)}`),
  attempts: (sid: number) => request<Attempt[]>(`/sessions/${sid}/attempts`),
  deleteSession: (sid: number) => request(`/sessions/${sid}`, json('DELETE')),
  syncPending: () => request<{ imported: number; failed: number }>('/sessions/sync-pending', json('POST')),

  games: () => request<GamesInfo>('/games'),
  gameStatus: () => request<GameStatus>('/games/status'),
  launchGame: (game: string, mode: string, patient_id: string) => request<GameStatus>('/games/launch', json('POST', { game, mode, patient_id })),
  stopGame: () => request<GameStatus & { message: string }>('/games/stop', json('POST')),
  gameLog: () => request<{ lines: string[] }>('/games/log'),

  datasets: () => request<DatasetFile[]>('/datasets'),
  signal: (file: string, points = 1200) => request<DatasetSignal>(`/datasets/signal${q({ file, points })}`),
  features: (file: string, window: number, step: number) => request<DatasetFeatures>(`/datasets/features${q({ file, window, step })}`),
  compare: () => request<DatasetCompare>('/datasets/compare'),

  settings: () => request<SettingsResponse>('/settings'),
  saveSettings: (raw: string) => request<SettingsResponse>('/settings', json('PUT', { raw })),
}
