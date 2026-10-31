import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, api, type PlanProgress } from './client'
import type { PlanRequest } from '../types'

const body: PlanRequest = {
  origin: 'Dallas, TX', destination: 'Denver, CO', departure: '2026-11-02T12:00:00Z', load_lbs: 36000, interval_miles: 25,
}

/** A streamed response delivering `chunks` one at a time, like a slow network. */
function streamed(chunks: string[], status = 200): Response {
  const encoder = new TextEncoder()
  const stream = new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk))
      controller.close()
    },
  })
  return new Response(stream, { status, headers: { 'Content-Type': 'application/x-ndjson' } })
}

function mockFetch(response: Response) {
  vi.stubGlobal('fetch', vi.fn(async () => response))
}

afterEach(() => vi.unstubAllGlobals())

describe('planStream', () => {
  it('reports progress lines, then resolves with the plan', async () => {
    mockFetch(streamed([
      '{"type":"progress","step":"places","message":"Looking up places"}\n',
      // A line split across two network chunks must still parse.
      '{"type":"progress","step":"rou',
      'tes","message":"Finding truck routes"}\n{"type":"result","plan":{"routes":[]}}\n',
    ]))
    const seen: PlanProgress[] = []
    const plan = await api.planStream(body, (p) => seen.push(p))
    expect(seen.map((p) => p.step)).toEqual(['places', 'routes'])
    expect(plan).toEqual({ routes: [] })
  })

  it('turns an error line into an ApiError with the server message', async () => {
    mockFetch(streamed(['{"type":"error","status":422,"detail":"Couldn\'t find a place called \'Qwxzzy\'."}\n']))
    const error = await api.planStream(body, () => {}).catch((e) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect(error.status).toBe(422)
    expect(error.message).toContain('Qwxzzy')
  })

  it('reports a stream that ends without a result', async () => {
    mockFetch(streamed(['{"type":"progress","step":"places","message":"…"}\n']))
    await expect(api.planStream(body, () => {})).rejects.toThrow('connection closed')
  })

  it('maps a 400 to per-field errors before any streaming', async () => {
    mockFetch(new Response(JSON.stringify({ load_lbs: ['Load must be at least 1 lb.'] }), { status: 400 }))
    const error = await api.planStream(body, () => {}).catch((e) => e)
    expect(error.status).toBe(400)
    expect(error.fieldErrors).toEqual({ load_lbs: ['Load must be at least 1 lb.'] })
  })

  it('reports a network failure in plain words', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('Failed to fetch') }))
    await expect(api.planStream(body, () => {})).rejects.toThrow("Can't reach the server")
  })
})
