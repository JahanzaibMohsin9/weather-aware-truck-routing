import { describe, expect, it } from 'vitest'
import type { Checkpoint, LngLat } from '../types'
import { MeasuredLine, haversineMi, mileAtTime, nearestHeatPoint } from './geo'

// About 69.09 miles per degree of latitude.
const MILES_PER_DEG = haversineMi([0, 0], [0, 1])
const north = (miles: number): LngLat[] => [[0, 0], [0, miles / MILES_PER_DEG]]

describe('MeasuredLine', () => {
  it('finds the point a given number of miles along', () => {
    const line = new MeasuredLine(north(100))
    expect(line.at(50)[1]).toBeCloseTo(50 / MILES_PER_DEG)
    expect(line.at(-5)).toEqual([0, 0])
    expect(line.at(500)).toEqual(north(100)[1])
  })

  it('scales simplified geometry to the real route length', () => {
    // The drawn line is 100 mi but the route is 200 mi: mile 100 is halfway along the drawing.
    const line = new MeasuredLine(north(100), 200)
    expect(line.at(100)[1]).toBeCloseTo(50 / MILES_PER_DEG)
  })

  it('slices the stretch between two miles', () => {
    const line = new MeasuredLine([[0, 0], [0, 0.5], [0, 1]])
    const part = line.slice(10, 60)
    expect(part[0][1]).toBeCloseTo(10 / MILES_PER_DEG)
    expect(part).toContainEqual([0, 0.5])
    expect(part.at(-1)![1]).toBeCloseTo(60 / MILES_PER_DEG)
  })
})

function cp(mile: number, eta: string): Checkpoint {
  return {
    mile, covers_mi: 0, lat: 0, lng: 0, eta,
    wind_mph: 0, gust_mph: 0, rain_in_hr: 0, snow_in_hr: 0, level: 'Low', level_value: 0, reasons: [],
  }
}

describe('mileAtTime', () => {
  const route = [cp(0, '2026-11-02T12:00:00Z'), cp(50, '2026-11-02T13:00:00Z'), cp(80, '2026-11-02T14:00:00Z')]

  it('interpolates between checkpoint ETAs', () => {
    expect(mileAtTime(route, Date.parse('2026-11-02T12:30:00Z'))).toBeCloseTo(25)
    expect(mileAtTime(route, Date.parse('2026-11-02T13:30:00Z'))).toBeCloseTo(65)
  })

  it('stays at the ends before departure and after arrival', () => {
    expect(mileAtTime(route, Date.parse('2026-11-02T10:00:00Z'))).toBe(0)
    expect(mileAtTime(route, Date.parse('2026-11-03T00:00:00Z'))).toBe(80)
  })
})

describe('nearestHeatPoint', () => {
  const points = [
    { lat: 40, lng: -100, score: [1, null] },
    { lat: 40.2, lng: -100, score: [2, 3] },
  ]

  it('picks the closest point with data for the hour', () => {
    expect(nearestHeatPoint(points, 0, [-100, 40.05], 30)).toBe(0)
    expect(nearestHeatPoint(points, 1, [-100, 40.05], 30)).toBe(1) // point 0 has no data at hour 1
  })

  it('returns -1 outside the corridor', () => {
    expect(nearestHeatPoint(points, 0, [-90, 40], 30)).toBe(-1)
  })
})
