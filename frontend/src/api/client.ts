import type { HeatmapResponse, LngLat, PlanRequest, PlanResponse } from '../types'

// In production the backend serves this page, so the API is on the same origin.
// In development Vite serves the page and the API runs on port 8000.
const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ?? (import.meta.env.DEV ? 'http://localhost:8000' : '')
).replace(/\/$/, '')

/** A failed request. `fieldErrors` holds DRF's per-field validation messages (HTTP 400). */
export class ApiError extends Error {
  status: number
  fieldErrors: Record<string, string[]>

  constructor(status: number, message: string, fieldErrors: Record<string, string[]> = {}) {
    super(message)
    this.status = status
    this.fieldErrors = fieldErrors
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init.headers },
    })
  } catch (error) {
    if ((error as Error).name === 'AbortError') throw error
    throw new ApiError(0, "Can't reach the server. Check your connection and try again.")
  }
  const body = await response.json().catch(() => null)
  if (response.ok) return body as T

  if (body && typeof body.detail === 'string') throw new ApiError(response.status, body.detail)
  if (response.status === 400 && body && typeof body === 'object') {
    const fieldErrors = Object.fromEntries(
      Object.entries(body).map(([field, messages]) => [field, ([] as string[]).concat(messages as string[])]),
    )
    throw new ApiError(400, 'Please fix the highlighted fields.', fieldErrors)
  }
  throw new ApiError(response.status, `The server returned an error (${response.status}). Please try again.`)
}

export const api = {
  health: (signal?: AbortSignal) => request<{ status: string }>('/api/health', { signal }),

  plan: (body: PlanRequest, signal?: AbortSignal) =>
    request<PlanResponse>('/api/plan', { method: 'POST', body: JSON.stringify(body), signal }),

  heatmap: (body: { routes: LngLat[][]; load_lbs: number; start: string }, signal?: AbortSignal) =>
    request<HeatmapResponse>('/api/heatmap', { method: 'POST', body: JSON.stringify(body), signal }),
}
