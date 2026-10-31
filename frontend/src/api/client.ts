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

const OFFLINE = "Can't reach the server. Check your connection and try again."

function isAbort(error: unknown): boolean {
  return (error as Error)?.name === 'AbortError'
}

async function send(path: string, init: RequestInit = {}): Promise<Response> {
  try {
    return await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init.headers },
    })
  } catch (error) {
    if (isAbort(error)) throw error
    throw new ApiError(0, OFFLINE)
  }
}

/** Turns an error response into an ApiError with a message for the user. */
async function failure(response: Response): Promise<ApiError> {
  const body = await response.json().catch(() => null)
  if (body && typeof body.detail === 'string') return new ApiError(response.status, body.detail)
  if (response.status === 400 && body && typeof body === 'object') {
    const fieldErrors = Object.fromEntries(
      Object.entries(body).map(([field, messages]) => [field, ([] as string[]).concat(messages as string[])]),
    )
    return new ApiError(400, 'Please fix the highlighted fields.', fieldErrors)
  }
  return new ApiError(response.status, `The server returned an error (${response.status}). Please try again.`)
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await send(path, init)
  if (!response.ok) throw await failure(response)
  return (await response.json()) as T
}

export interface PlanProgress {
  step: string
  message: string
}

/**
 * POST /api/plan/stream: the server sends one JSON object per line, progress
 * first and then the result, so the user sees what the wait is spent on.
 */
async function planStream(
  body: PlanRequest,
  onProgress: (progress: PlanProgress) => void,
  signal?: AbortSignal,
): Promise<PlanResponse> {
  const response = await send('/api/plan/stream', { method: 'POST', body: JSON.stringify(body), signal })
  if (!response.ok || !response.body) throw await failure(response)

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  try {
    for (;;) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += value
      let newline
      while ((newline = buffer.indexOf('\n')) >= 0) {
        const line = buffer.slice(0, newline).trim()
        buffer = buffer.slice(newline + 1)
        if (!line) continue
        const event = JSON.parse(line)
        if (event.type === 'progress') onProgress({ step: event.step, message: event.message })
        else if (event.type === 'result') return event.plan as PlanResponse
        else if (event.type === 'error') throw new ApiError(event.status, event.detail)
      }
    }
  } catch (error) {
    if (error instanceof ApiError || isAbort(error)) throw error
    throw new ApiError(0, OFFLINE)
  }
  throw new ApiError(0, 'The connection closed before the plan finished. Please try again.')
}

export const api = {
  health: (signal?: AbortSignal) => request<{ status: string }>('/api/health', { signal }),

  plan: (body: PlanRequest, signal?: AbortSignal) =>
    request<PlanResponse>('/api/plan', { method: 'POST', body: JSON.stringify(body), signal }),

  planStream,

  places: (query: string, signal?: AbortSignal) =>
    request<{ places: { label: string; lat: number; lng: number }[] }>(
      `/api/places?q=${encodeURIComponent(query)}`,
      { signal },
    ),

  heatmap: (body: { routes: LngLat[][]; load_lbs: number; start: string }, signal?: AbortSignal) =>
    request<HeatmapResponse>('/api/heatmap', { method: 'POST', body: JSON.stringify(body), signal }),
}
