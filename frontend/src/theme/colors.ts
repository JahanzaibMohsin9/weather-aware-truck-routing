import type { LevelLabel } from '../types'

// Risk colours run green -> yellow -> orange -> red -> deep purple, so No Travel
// reads as "worse than red" and isn't confused with a route colour.
export const LEVELS: { label: LevelLabel; value: number; color: string }[] = [
  { label: 'Low', value: 0, color: '#2e7d32' },
  { label: 'Moderate', value: 1, color: '#f9a825' },
  { label: 'High', value: 2, color: '#ef6c00' },
  { label: 'Severe', value: 3, color: '#c62828' },
  { label: 'No Travel', value: 4, color: '#4a148c' },
]

export const NO_FORECAST_COLOR = '#9e9e9e'

export function levelColor(level: LevelLabel): string {
  return LEVELS.find((l) => l.label === level)?.color ?? NO_FORECAST_COLOR
}

// Route colours are kept away from the risk palette.
export const ROUTE_COLORS: Record<string, string> = {
  A: '#1e88e5',
  B: '#00897b',
  C: '#6d4c41',
}
