# API

Base path: `/api`. Requests and responses are JSON. Times are ISO 8601; responses use UTC (`Z`). Coordinates in `geometry` are `[lng, lat]` (GeoJSON order); elsewhere they are named `lat` and `lng`.

## `GET /api/health`

Returns `{"status": "ok"}`. Used by the frontend and the host's health check.

## `POST /api/plan`

*Implemented.*

Plans three routes and scores them. If the routing API returns fewer than three, the backend makes extra requests (other route types, then a sideways via-point) and drops near-duplicates. Fewer than three are returned only when no distinct alternative exists, and the response says so in `notes`.

### Request

```json
{
  "origin": "Dallas, TX",
  "destination": "Denver, CO",
  "departure": "2026-11-02T06:00:00-06:00",
  "load_lbs": 36000,
  "interval_miles": 25
}
```

| Field | Type | Rules |
|---|---|---|
| `origin`, `destination` | string | Required, up to 200 characters, must differ (case and spacing ignored). US places only. |
| `departure` | datetime | Required. Not more than 5 minutes in the past, at most 14 days ahead. Without an offset it is read as UTC. |
| `load_lbs` | number | Required, 1–150,000 |
| `interval_miles` | integer | 10, 25 or 50; default 25 |

### Response `200`

Trimmed example based on a real Dallas → Denver plan (one route, one checkpoint, coordinates illustrative):

```json
{
  "origin": { "label": "Dallas, TX", "lat": 32.778, "lng": -96.796 },
  "destination": { "label": "Denver, CO", "lat": 39.738, "lng": -104.985 },
  "departure": "2026-10-31T13:47:00Z",
  "load_lbs": 36000,
  "interval_miles": 25,
  "routes": [
    {
      "id": "C",
      "rank": 3,
      "recommended": false,
      "source": "via",
      "geometry": [[-96.796, 32.778], [-96.799, 32.781]],
      "distance_mi": 888.3,
      "duration_min": 781.2,
      "summary": {
        "no_travel_mi": 0, "severe_mi": 0, "high_mi": 0, "no_forecast_mi": 0,
        "avg_risk": 0.028, "has_no_travel": false, "forecast_complete": true
      },
      "checkpoints": [
        {
          "mile": 550,
          "covers_mi": 25,
          "lat": 37.12, "lng": -101.33,
          "eta": "2026-10-31T20:33:39Z",
          "wind_mph": 6.6, "gust_mph": 16.6,
          "rain_in_hr": 0.157, "snow_in_hr": 0.0,
          "level": "Moderate",
          "level_value": 1,
          "reasons": ["Rain 0.16 in/hr: Moderate"]
        }
      ]
    }
  ],
  "recommended_route_id": "A",
  "explanation": "Route A: same weather risk as Route B and 36 min faster.",
  "notes": []
}
```

| Field | Meaning |
|---|---|
| `origin.label`, `destination.label` | The place the text was matched to. Show it, so the driver can spot "Springfield, MO" when they meant Illinois. |
| `rank` | 1 = best. Routes keep their A/B/C order; `rank` gives the recommendation order. |
| `source` | How the route was found: `fastest`, `alternative`, `shortest`, `eco` or `via` |
| `geometry` | Simplified to ~50 m precision (about 500–1,500 points per route) |
| `distance_mi`, `mile` | Measured along the route geometry |
| `covers_mi` | Miles of road this checkpoint stands for (half the gap to each neighbour) |
| `level` | `Low`, `Moderate`, `High`, `Severe`, `No Travel`, or `No Forecast` when the ETA is past the forecast range |
| `level_value` | 0–4, or `null` for No Forecast |
| `reasons` | Which thresholds and load rules set the level; empty for Low |

- Summary and checkpoint values are unrounded; the UI rounds them for display.
- `recommended_route_id` is `null` when every route has a No Travel checkpoint.
- `notes` lists anything the driver should know, such as fewer than three distinct routes or an incomplete forecast.

### Errors

Errors other than `400` have the body `{ "detail": "message for the user" }`.

| Status | When |
|---|---|
| `400` | Validation failed; body is `{ "field": ["message"] }` |
| `422` | A place couldn't be found (or only a weak fuzzy match, e.g. "asdf" → "Asaf Drive"), no truck route exists, or origin and destination are the same place |
| `502` | The routing or weather provider failed after one retry. No partial plan is returned. |

## `POST /api/heatmap`

*Implemented.* Weather risk on a grid along the trip corridor for 49 hours. The client sends the checkpoints it got from `/api/plan`, so the server stores no plan state between requests.

### Request

```json
{
  "routes": [
    [[-96.797, 32.777], [-97.02, 33.01]],
    [[-96.797, 32.777], [-96.91, 33.05]]
  ],
  "load_lbs": 36000,
  "start": "2026-11-02T12:00Z"
}
```

| Field | Type | Meaning |
|---|---|---|
| `routes` | array of `[lng, lat]` lists | 1–3 routes, each its checkpoints in order (up to 500); they define the corridor |
| `load_lbs` | number | Load weight, so heatmap levels match the checkpoint levels |
| `start` | datetime | Hour 0. Rounded down to the hour; at most 14 days ahead |

### Response `200`

```json
{
  "hours": ["2026-11-02T12:00:00Z", "2026-11-02T13:00:00Z"],
  "spacing_mi": 23.9,
  "points": [
    {
      "lat": 33.1, "lng": -97.4,
      "level": [0, 0, 1, 2],
      "score": [0.48, 0.58, 1.61, 2.1],
      "wind": [12.0, 14.5, 26.1, 36.0],
      "rain": [0.0, 0.0, 0.12, 0.3],
      "snow": [0.0, 0.0, 0.0, 0.0]
    }
  ]
}
```

| Field | Meaning |
|---|---|
| `hours` | 49 hourly timestamps, hour 0 to hour 48 |
| `spacing_mi` | Distance between grid points. The map uses it to size the heat radius. |
| `level` | 0–4, the same thresholds and load rules as the checkpoints |
| `score` | Continuous 0–4 for drawing the heat; its whole part always equals `level` (see [risk model](risk-model.md#heat-score)) |
| `wind`, `rain`, `snow` | mph, in/hr (rain + showers), in/hr |

Each array has one value per hour. An hour without forecast data is `null` in every array and is drawn as no heat, never as Low. A typical long trip is about 170–200 points and about 220 KB of JSON, which gzip brings to about 30 KB.

### Errors

`400` for invalid input, `502` if the weather service fails after one retry.
