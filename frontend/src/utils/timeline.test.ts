import { describe, expect, it } from 'vitest'
import type { Checkpoint, LevelLabel } from '../types'
import { routeTimeline } from './timeline'

const HOUR0 = '2026-11-02T12:00:00Z'
const at = (hours: number) => new Date(Date.parse(HOUR0) + hours * 3_600_000).toISOString()

function cp(mile: number, hours: number, level: LevelLabel = 'Low'): Checkpoint {
  return {
    mile, covers_mi: 0, lat: 0, lng: 0, eta: at(hours),
    wind_mph: 5, gust_mph: 9, rain_in_hr: 0, snow_in_hr: 0, level, level_value: 0, reasons: [],
  }
}

describe('routeTimeline', () => {
  it('splits time at the midpoints between checkpoint ETAs', () => {
    const { segments, arrival } = routeTimeline([cp(0, 1), cp(25, 3, 'High'), cp(50, 5)], HOUR0, 48)
    expect(segments.map((s) => [s.start, s.end, s.level])).toEqual([
      [1, 2, 'Low'],
      [2, 4, 'High'],
      [4, 5, 'Low'],
    ])
    expect(arrival).toBe(5)
  })

  it('cuts off what falls outside the slider range', () => {
    const { segments, arrival } = routeTimeline([cp(0, 40), cp(25, 46, 'Severe'), cp(50, 52)], HOUR0, 48)
    expect(segments.map((s) => [s.start, s.end])).toEqual([
      [40, 43],
      [43, 48],
    ])
    expect(arrival).toBe(52)
  })

  it('drops checkpoints entirely before hour 0', () => {
    const { segments } = routeTimeline([cp(0, -3), cp(25, -1), cp(50, 1)], HOUR0, 48)
    expect(segments.map((s) => s.checkpoint.mile)).toEqual([50])
  })
})
