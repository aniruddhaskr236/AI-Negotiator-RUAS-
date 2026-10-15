export type CallStatus = "idle" | "ringing" | "talking" | "done" | "failed" | "retrying"
export type Speaker = "agent" | "shop"
export type Language = "en" | "hi" | "kn"

export type TranscriptTurn = {
  speaker: Speaker
  text: string
  translation?: string
  lang: Language
  ts: string | number
  confidence?: number
}

export type Shop = {
  id: string
  call_id?: string
  name: string
  status: CallStatus
  first_price: number | null
  final_price: number | null
  warranty_months: number | null
  eta_days: number | null
  part_type: string
  conditions: string
  error?: string
  lang?: Language
  transcript: TranscriptTurn[]
}

export type Weights = {
  price: number
  warranty: number
  speed: number
  quality: number
}

export type JobNeed = {
  job_id?: string
  need: string
  weights: Weights
}

export type TimelineEvent = {
  ts: number
  text: string
  call_id?: string
}

export type ConflictEvent = {
  call_id: string
  field: string
  old_value: string
  new_value: string
  old_ts: number
  new_ts: number
}

export type EvidenceItem = {
  turn_ts: number
  text: string
  translation?: string | null
  lang: string
  audio_url?: string | null
}

export type ReportRow = {
  call_id: string
  shop_name: string
  rank: number
  score: number
  first_price: number | null
  final_price: number | null
  saving: number
  warranty_months: number | null
  eta_days: number | null
  part_type: string
  conditions: string
  evidence: Record<string, EvidenceItem>
}

export type RecommendedShop = {
  call_id: string
  shop_name: string
  reason: string
}

export type OtherShop = {
  call_id: string
  why_not: string
}

export type Report = {
  job_id: string
  recommended?: RecommendedShop | null
  weights: Weights
  rows: ReportRow[]
  others: OtherShop[]
  caveats: string[]
  timeline: TimelineEvent[]
}

export type CheckItem = {
  name: string
  ok: boolean
  latency_ms: number
  detail: string
}

export type CheckResponse = {
  checks: CheckItem[]
}
