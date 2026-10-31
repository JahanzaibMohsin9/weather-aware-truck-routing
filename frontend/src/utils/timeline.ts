import type { Checkpoint, LevelLabel } from '../types'

export interface TimelineSegment {
  /** Hours after the forecast's hour 0, clamped to [0, totalHours]. */
  start: number
  end: number
  level: LevelLabel
  checkpoint: Checkpoint
}

export interface RouteTimeline {
  segments: TimelineSegment[]
  /** Hours from hour 0 to arrival (may be past the end of the scale). */
  arrival: number
}

const HOUR_MS = 3_600_000

/**
 * When the truck is in each checkpoint's stretch of road, on the forecast
 * slider's scale. Each checkpoint covers the time from halfway since the
 * previous checkpoint to halfway to the next, matching how its miles are
 * counted (nearest checkpoint). Parts outside [0, totalHours] are cut off.
 */
export function routeTimeline(checkpoints: Checkpoint[], hour0: string, totalHours: number): RouteTimeline {
  const origin = Date.parse(hour0)
  const at = checkpoints.map((cp) => (Date.parse(cp.eta) - origin) / HOUR_MS)
  const segments: TimelineSegment[] = []
  checkpoints.forEach((cp, i) => {
    const from = i === 0 ? at[0] : (at[i - 1] + at[i]) / 2
    const to = i === checkpoints.length - 1 ? at[i] : (at[i] + at[i + 1]) / 2
    const start = Math.max(0, from)
    const end = Math.min(totalHours, to)
    if (end > start) segments.push({ start, end, level: cp.level, checkpoint: cp })
  })
  return { segments, arrival: at[at.length - 1] ?? 0 }
}
