import type { CheckResponse, Report, Weights } from "@/types"

export async function createJob(need: string, weights: Weights) {
  const res = await fetch("/api/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ need, weights }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to create job`)
  return await res.json() as { job_id: string; calls: Array<{ call_id: string; shop_id: string; shop_name: string; lang: string }> }
}

export async function retryCall(jobId: string, callId: string) {
  const res = await fetch(`/api/jobs/${jobId}/calls/${callId}/retry`, {
    method: "POST",
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to retry call`)
  return await res.json() as { ok: boolean }
}

export async function getReport(jobId: string, weightsQuery?: string) {
  const url = weightsQuery
    ? `/api/jobs/${jobId}/report?weights=${weightsQuery}`
    : `/api/jobs/${jobId}/report`
  const res = await fetch(url)
  if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to fetch report`)
  return await res.json() as Report
}

export async function getCheck() {
  const res = await fetch("/api/check")
  if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to run checks`)
  return await res.json() as CheckResponse
}

export async function triggerDemoFail(kind: "hangup" | "price_change" | "kill_provider" | "unclear_audio", callId?: string) {
  const res = await fetch("/api/demo/fail", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ kind, call_id: callId }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to trigger demo fail`)
  return await res.json() as { ok: boolean }
}
