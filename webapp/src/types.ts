export interface Patient {
  patient_id: string
  age: number | null
  affected_side: string | null
  stroke_date: string | null
  notes: string | null
}

export interface PatientSummary extends Patient {
  sessions: number
  avg_accuracy: number | null
  last_session: string | null
  best_score: number | null
  recent_accuracy: number[]
  trend: number | null
  last_game: string | null
}

export interface Session {
  session_id: number
  patient_id: string
  game_name: string
  started_at: string
  ended_at: string | null
  total_score: number
  duration_s: number
  accuracy: number
  attempts?: number
}

export interface Attempt {
  attempt_id: number
  session_id: number
  ts: string
  target_movement: string
  detected_movement: string
  vision_label: string | null
  correct: number
  reaction_time_ms: number
  emg_rms: number
  emg_mav: number
  confidence: number
}

export interface MovementAccuracy {
  target_movement: string
  accuracy: number
  attempts: number
}

export interface Overview {
  patients: number
  sessions: number
  attempts: number
  avg_accuracy: number
  total_minutes: number
  avg_reaction_ms: number | null
  recent_sessions: Session[]
  sessions_by_game: { game_name: string; sessions: number; accuracy: number; avg_score: number }[]
  daily: { day: string; sessions: number; accuracy: number }[]
  movement_accuracy: MovementAccuracy[]
  pending_sessions: number
}

export interface Progress {
  sessions: Session[]
  movement_accuracy: MovementAccuracy[]
  emg_activity_by_movement: { movement: string; mean_rms: number | null; mean_mav: number | null; attempts: number }[]
}

export interface GameDef {
  id: string
  name: string
  modes: string[]
  description: string
  trains?: string[]
}

export interface GamesInfo {
  games: GameDef[]
  modes: Record<string, string>
}

export interface GameStatus {
  running: boolean
  pid: number | null
  last: {
    game: string
    game_name: string
    mode: string
    patient_id: string
    difficulty?: string
    duration_s?: number
    started_at: string
    exit_code: number | null
  } | null
}

export interface DatasetFile {
  file: string
  name: string
  group: string
  folder: string
  category: 'normal' | 'filtered' | 'patient' | 'recorded'
  rows: number
  columns: string[]
  size_kb: number
}

export interface DatasetSignal {
  file: string
  rows: number
  columns: string[]
  index: number[]
  series: Record<string, (number | null)[]>
  labels: string[] | null
}

export interface FeatureRow {
  movement: string
  RMS?: number
  MAV?: number
  VAR?: number
  STD?: number
  PEAK?: number
  WL?: number
  samples?: number
}

export interface DatasetFeatures {
  file: string
  window: number
  step: number
  features: FeatureRow[]
  rms_series: Record<string, number[]>
}

export interface DatasetCompare {
  categories: Record<string, { movement: string; RMS: number; MAV: number; RMS_std: number; files: number }[]>
  files: Record<string, number>
}

export interface SettingsResponse {
  settings: Record<string, unknown>
  labels: string[]
  raw: string
}
