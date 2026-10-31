import type { Condition } from '../types'

export type HeatMode = 'risk' | Condition

/**
 * A value's position on a 0–4 scale, linear between band starts: 0 at zero,
 * 1 where Moderate starts, 2 at High, 3 at Severe, 4 at No Travel and above.
 * Matches the backend's heat score for a single condition (without load rules),
 * using the band starts the heatmap response provides.
 */
export function scalePosition(value: number, bandStarts: number[]): number {
  const knots = [0, ...bandStarts]
  if (value >= knots[knots.length - 1]) return 4
  for (let i = 1; i < knots.length; i++) {
    if (value < knots[i]) return i - 1 + (value - knots[i - 1]) / (knots[i] - knots[i - 1])
  }
  return 4
}
