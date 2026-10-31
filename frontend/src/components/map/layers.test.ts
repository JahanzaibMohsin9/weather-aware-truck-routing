import { describe, expect, it } from 'vitest'
import type { HeatmapResponse, Route } from '../../types'
import { MeasuredLine } from '../../utils/geo'
import { heatFrames, riskSegments } from './layers'

const heatmap: HeatmapResponse = {
  hours: ['2026-11-02T12:00:00Z', '2026-11-02T13:00:00Z'],
  spacing_mi: 20,
  scales: { wind: [25, 35, 45, 55], rain: [0.1, 0.25, 0.5, 1], snow: [0.5, 1, 2, 3] },
  points: [
    { lat: 40, lng: -100, level: [0, 2], score: [0.4, 2.1], wind: [10, 36], rain: [0, 0], snow: [0, 0] },
    { lat: 41, lng: -100, level: [1, null], score: [1.5, null], wind: [30, null], rain: [0.375, null], snow: [0, null] },
  ],
}

describe('heatFrames', () => {
  it('builds one frame per hour and leaves out points without data', () => {
    const frames = heatFrames(heatmap)
    expect(frames).toHaveLength(2)
    expect(frames[0].features).toHaveLength(2)
    expect(frames[1].features).toHaveLength(1)
    expect(frames[1].features[0].properties).toEqual({ score: 2.1, level: 2 })
  })

  it('shades one condition on its own threshold scale', () => {
    const wind = heatFrames(heatmap, 'wind')
    expect(wind[0].features.map((f) => f.properties!.score)).toEqual([0.4, 1.5])
    const rain = heatFrames(heatmap, 'rain')
    expect(rain[0].features[1].properties!.score).toBeCloseTo(2.5)
  })
})

describe('riskSegments', () => {
  it("cuts the selected route into each checkpoint's stretch, coloured by level", () => {
    const route = {
      id: 'A',
      distance_mi: 2 * 69.09,
      geometry: [[0, 0], [0, 2]],
      checkpoints: [
        { covers_mi: 34.5, level: 'Low' },
        { covers_mi: 69.1, level: 'Severe' },
        { covers_mi: 34.5, level: 'Low' },
      ],
    } as unknown as Route
    const line = new MeasuredLine(route.geometry, route.distance_mi)
    const { features } = riskSegments(route, line)
    expect(features.map((f) => f.properties!.color)).toEqual(['#2e7d32', '#c62828', '#2e7d32'])
    expect(features[1].geometry.coordinates[0][1]).toBeCloseTo(0.5, 1)
    expect(features[1].geometry.coordinates.at(-1)![1]).toBeCloseTo(1.5, 1)
  })

  it('is empty with no selected route', () => {
    expect(riskSegments(undefined, undefined).features).toEqual([])
  })
})
