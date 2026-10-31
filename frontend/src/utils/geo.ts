import type { Checkpoint, LngLat } from '../types'

const EARTH_RADIUS_MI = 3958.7613
const rad = (deg: number) => (deg * Math.PI) / 180

export function haversineMi([lng1, lat1]: LngLat, [lng2, lat2]: LngLat): number {
  const h =
    Math.sin(rad(lat2 - lat1) / 2) ** 2 +
    Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(rad(lng2 - lng1) / 2) ** 2
  return 2 * EARTH_RADIUS_MI * Math.asin(Math.min(1, Math.sqrt(h)))
}

/** A polyline with the distance to each vertex, for repeated lookups by mile. */
export class MeasuredLine {
  readonly points: LngLat[]
  readonly cum: number[]
  /** Scales the simplified geometry's length to the route's real length. */
  private readonly scale: number

  constructor(points: LngLat[], routeMiles?: number) {
    this.points = points
    this.cum = [0]
    for (let i = 1; i < points.length; i++) this.cum.push(this.cum[i - 1] + haversineMi(points[i - 1], points[i]))
    const length = this.cum[this.cum.length - 1]
    this.scale = routeMiles && length > 0 ? length / routeMiles : 1
  }

  /** Position `mile` route-miles from the start. */
  at(mile: number): LngLat {
    const d = mile * this.scale
    const { points, cum } = this
    if (d <= 0) return points[0]
    if (d >= cum[cum.length - 1]) return points[points.length - 1]
    let lo = 0
    let hi = cum.length - 1
    while (hi - lo > 1) {
      const mid = (lo + hi) >> 1
      if (cum[mid] <= d) lo = mid
      else hi = mid
    }
    const t = (d - cum[lo]) / (cum[hi] - cum[lo])
    const [x1, y1] = points[lo]
    const [x2, y2] = points[hi]
    return [x1 + t * (x2 - x1), y1 + t * (y2 - y1)]
  }

  /** The part of the line between two route-miles. */
  slice(fromMile: number, toMile: number): LngLat[] {
    const a = fromMile * this.scale
    const b = toMile * this.scale
    const inside = this.points.filter((_, i) => this.cum[i] > a && this.cum[i] < b)
    return [this.at(fromMile), ...inside, this.at(toMile)]
  }
}

/**
 * Miles along the route the truck has covered at `time`, interpolated between
 * checkpoint ETAs. Before departure it is 0; after arrival, the full distance.
 */
export function mileAtTime(checkpoints: Checkpoint[], time: number): number {
  const first = checkpoints[0]
  const last = checkpoints[checkpoints.length - 1]
  if (time <= Date.parse(first.eta)) return first.mile
  if (time >= Date.parse(last.eta)) return last.mile
  for (let i = 1; i < checkpoints.length; i++) {
    const t1 = Date.parse(checkpoints[i].eta)
    if (time <= t1) {
      const t0 = Date.parse(checkpoints[i - 1].eta)
      const frac = t1 === t0 ? 0 : (time - t0) / (t1 - t0)
      return checkpoints[i - 1].mile + frac * (checkpoints[i].mile - checkpoints[i - 1].mile)
    }
  }
  return last.mile
}
