import type { FeatureCollection, LineString, Point } from 'geojson'
import type { HeatmapLayerSpecification } from 'react-map-gl/maplibre'
import type { HeatmapResponse, Route } from '../../types'
import { levelColor, ROUTE_COLORS } from '../../theme/colors'
import { MeasuredLine } from '../../utils/geo'

export const ROUTE_CASING_LAYER = 'routes-casing'
export const ROUTE_LINE_LAYER = 'routes-line'
export const CHECKPOINT_LAYER = 'checkpoints'

/** All routes; the selected one is drawn on top and wider. */
export function routeLines(routes: Route[], selectedId: string | null): FeatureCollection<LineString> {
  return {
    type: 'FeatureCollection',
    features: routes.map((route) => ({
      type: 'Feature',
      properties: { id: route.id, color: ROUTE_COLORS[route.id], selected: route.id === selectedId },
      geometry: { type: 'LineString', coordinates: route.geometry },
    })),
  }
}

/** The selected route cut into the stretch each checkpoint covers, coloured by its level. */
export function riskSegments(route: Route | undefined, line: MeasuredLine | undefined): FeatureCollection<LineString> {
  if (!route || !line) return { type: 'FeatureCollection', features: [] }
  let start = 0
  return {
    type: 'FeatureCollection',
    features: route.checkpoints.map((cp) => {
      const end = start + cp.covers_mi
      const feature = {
        type: 'Feature' as const,
        properties: { color: levelColor(cp.level) },
        geometry: { type: 'LineString' as const, coordinates: line.slice(start, end) },
      }
      start = end
      return feature
    }),
  }
}

export function checkpointPoints(routes: Route[], selectedId: string | null): FeatureCollection<Point> {
  // Selected route last, so its dots draw on top.
  const ordered = [...routes].sort((a, b) => Number(a.id === selectedId) - Number(b.id === selectedId))
  return {
    type: 'FeatureCollection',
    features: ordered.flatMap((route) =>
      route.checkpoints.map((cp, index) => ({
        type: 'Feature' as const,
        properties: { route: route.id, index, color: levelColor(cp.level), selected: route.id === selectedId },
        geometry: { type: 'Point' as const, coordinates: [cp.lng, cp.lat] },
      })),
    ),
  }
}

/**
 * One FeatureCollection per forecast hour, built once. Moving the slider just
 * swaps which one the heatmap source shows; nothing is fetched or recomputed.
 * Points with no forecast for an hour are left out (no heat, never "Low").
 */
export function heatFrames(heatmap: HeatmapResponse): FeatureCollection<Point>[] {
  return heatmap.hours.map((_, hour) => ({
    type: 'FeatureCollection',
    features: heatmap.points
      .filter((p) => p.score[hour] != null)
      .map((p) => ({
        type: 'Feature' as const,
        properties: { score: p.score[hour], level: p.level[hour] },
        geometry: { type: 'Point' as const, coordinates: [p.lng, p.lat] },
      })),
  }))
}

/**
 * Heatmap radius that keeps neighbouring grid points overlapping at every
 * zoom. MapLibre draws the world 512 px wide at zoom 0, doubling per level.
 */
export function heatRadius(spacingMi: number, latitude: number): HeatPaint['heatmap-radius'] {
  const milesAroundWorld = 24901 * Math.cos((latitude * Math.PI) / 180)
  const pxPerMileAtZoom0 = 512 / milesAroundWorld
  const r0 = 1.5 * spacingMi * pxPerMileAtZoom0
  return ['interpolate', ['exponential', 2], ['zoom'], 0, r0, 12, r0 * 4096]
}

type HeatPaint = NonNullable<HeatmapLayerSpecification['paint']>

/**
 * With radius = 1.5 × grid spacing, MapLibre's Gaussian kernels from a uniform
 * grid add up to about 0.62 × weight; this intensity brings a uniform field
 * back to density ≈ weight, so colour ≈ heat score / 4.
 */
export const HEAT_INTENSITY = 1.6

/** Density (score / 4) -> colour, matching the risk levels' colours. */
export const HEAT_COLOR: HeatPaint['heatmap-color'] = [
  'interpolate',
  ['linear'],
  ['heatmap-density'],
  0, 'rgba(46,125,50,0)',
  0.05, 'rgba(46,125,50,0.15)',
  0.2, 'rgba(46,125,50,0.35)',
  0.25, 'rgba(249,168,37,0.55)',
  0.5, 'rgba(239,108,0,0.65)',
  0.75, 'rgba(198,40,40,0.72)',
  1, 'rgba(74,20,140,0.8)',
]
