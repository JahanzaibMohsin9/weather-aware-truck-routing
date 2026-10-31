# API

Base path: `/api`. Requests and responses are JSON. Times are ISO 8601; responses use UTC (`Z`). Coordinates in `geometry` are `[lng, lat]` (GeoJSON order); elsewhere they are named `lat` and `lng`.

> The contract below is the planned shape and will be updated if implementation changes it.

## `POST /api/plan`

Plans up to three routes and scores them.

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
| `origin`, `destination` | string | Required, must differ |
| `departure` | datetime with offset | Required, not in the past |
| `load_lbs` | number | Required, > 0 |
| `interval_miles` | integer | 10, 25 or 50; default 25 |

### Response `200`

```json
{
  "routes": [
    {
      "id": "A",
      "geometry": [[-96.797, 32.777], [-96.80, 32.79]],
      "distance_mi": 795.2,
      "duration_min": 742,
      "summary": { "no_travel_mi": 0, "severe_mi": 25, "high_mi": 50, "avg_risk": 0.82 },
      "checkpoints": [
        {
          "mile": 25,
          "lat": 33.01, "lng": -97.02,
          "eta": "2026-11-02T12:31:00Z",
          "wind_mph": 22.1, "gust_mph": 30.4,
          "rain_in_hr": 0.0, "snow_in_hr": 0.0,
          "level": "Low",
          "reasons": []
        }
      ]
    }
  ],
  "recommended_route_id": "B",
  "explanation": "Route B: 0 severe miles vs 25 on Route A; 18 min longer."
}
```

`level` is one of `Low`, `Moderate`, `High`, `Severe`, `No Travel`, or `No Forecast` when the ETA is past the forecast range. `recommended_route_id` is `null` when every route has a No Travel segment.

### Errors

| Status | When |
|---|---|
| `400` | Validation failed; body is `{ "field": ["message"] }` |
| `422` | A place could not be geocoded, or no route was found |
| `502` | The routing or weather provider failed |

## `GET /api/heatmap`

Weather risk on a grid along the trip corridor for 49 hours.

### Query

| Param | Example | Meaning |
|---|---|---|
| `bbox` | `-105.2,32.5,-96.5,39.9` | `minLng,minLat,maxLng,maxLat` of the routes |
| `start` | `2026-11-02T12:00Z` | Hour 0 (the departure hour) |
| `load_lbs` | `36000` | Load weight, so heatmap colours match the checkpoint levels |

### Response `200`

```json
{
  "hours": ["2026-11-02T12:00Z", "2026-11-02T13:00Z"],
  "points": [
    {
      "lat": 33.1, "lng": -97.4,
      "risk": [0, 0, 1, 2],
      "wind": [12.0, 14.5, 26.1, 36.0],
      "rain": [0.0, 0.0, 0.12, 0.3],
      "snow": [0.0, 0.0, 0.0, 0.0]
    }
  ]
}
```

`hours` has 49 entries and each point's arrays have one value per hour. `risk` (0–4) uses the same thresholds and load rules as the checkpoints, so a checkpoint and the heatmap under it show the same level for the same hour.
