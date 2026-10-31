// Shapes returned by the backend. See docs/api.md.

export type LevelLabel = 'Low' | 'Moderate' | 'High' | 'Severe' | 'No Travel' | 'No Forecast'

export type LngLat = [number, number]

export interface Place {
  label: string
  lat: number
  lng: number
}

export interface Checkpoint {
  mile: number
  covers_mi: number
  lat: number
  lng: number
  eta: string
  wind_mph: number | null
  gust_mph: number | null
  rain_in_hr: number | null
  snow_in_hr: number | null
  level: LevelLabel
  level_value: number | null
  reasons: string[]
}

export interface RouteSummary {
  no_travel_mi: number
  severe_mi: number
  high_mi: number
  no_forecast_mi: number
  avg_risk: number | null
  has_no_travel: boolean
  forecast_complete: boolean
}

export interface Route {
  id: string
  rank: number
  recommended: boolean
  source: string
  geometry: LngLat[]
  distance_mi: number
  duration_min: number
  summary: RouteSummary
  checkpoints: Checkpoint[]
}

export interface PlanResponse {
  origin: Place
  destination: Place
  departure: string
  load_lbs: number
  interval_miles: number
  routes: Route[]
  recommended_route_id: string | null
  explanation: string
  notes: string[]
}

export interface PlanRequest {
  origin: string
  destination: string
  departure: string
  load_lbs: number
  interval_miles: number
}

export interface HeatPoint {
  lat: number
  lng: number
  level: (number | null)[]
  score: (number | null)[]
  wind: (number | null)[]
  rain: (number | null)[]
  snow: (number | null)[]
}

export type Condition = 'wind' | 'rain' | 'snow'

export interface HeatmapResponse {
  hours: string[]
  spacing_mi: number
  /** Where each band starts for each condition: [Moderate, High, Severe, No Travel]. */
  scales: Record<Condition, number[]>
  points: HeatPoint[]
}
