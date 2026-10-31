# Architecture

## Overview

```
┌──────────────── Browser (React + MUI + MapLibre) ────────────────┐
│  Plan form → route cards → map (routes, checkpoints, heatmap)    │
│  Forecast slider changes the heatmap hour locally, no requests   │
└───────────────┬───────────────────────────────┬──────────────────┘
                │ POST /api/plan                │ POST /api/heatmap
┌───────────────▼───────────────────────────────▼──────────────────┐
│ Django + DRF                                                     │
│  views / serializers   →  validate input, shape responses        │
│  services/             →  TomTom (geocode, routes), Open-Meteo,  │
│                           corridor grid; responses cached        │
│  domain/               →  pure Python: geometry, checkpoints,    │
│                           risk rules, route ranking              │
└──────────────────────────────────────────────────────────────────┘
```

`domain/` has no HTTP or Django imports. It takes plain data and returns plain data, so the rules can be unit-tested without the network and read in one place.

## Planning a trip (`POST /api/plan`)

1. **Validate** the request: origin and destination differ, load > 0, interval is 10, 25 or 50, departure is not in the past and at most 14 days ahead.
2. **Geocode** origin and destination.
3. **Get routes** from TomTom in truck mode with the load weight and two alternatives (3 routes total). If fewer come back, the backend tops up with other route types and then a via-point pushed sideways from the main route, and drops near-duplicates. Only when no distinct third route exists does it return fewer, and the response says so; the app doesn't make routes up.
4. **Place checkpoints** by walking each route's polyline with haversine distance and dropping a point every N miles, plus the start and end.
5. **Estimate ETAs:** departure time plus the routing API's cumulative travel time at that point along the route. All times are UTC internally and shown in local time in the browser.
6. **Fetch weather** for all checkpoints in batched Open-Meteo requests and read the value for each checkpoint's ETA. If the weather API fails, the whole request fails rather than returning a plan with gaps.
7. **Classify** each checkpoint, assign each mile of road to its nearest checkpoint, and **rank** the routes (see [risk model](risk-model.md)).
8. **Respond** with routes, checkpoints, summaries, the recommended route and a one-line reason for the pick.

## Heatmap (`POST /api/heatmap`)

The forecast slider has to feel instant, so the heatmap is built to need no network calls while the slider moves.

1. The browser posts each route's checkpoints, the load weight and the departure hour. Checkpoints 10–50 miles apart are precise enough to trace a 30-mile corridor, and sending them keeps the server stateless: no plan has to be stored between the two requests, which matters on hosting where each worker process has its own memory cache.
2. The backend builds a grid of points over the checkpoints' bounding box and keeps only points within about 30 miles of a route (the trip corridor), up to roughly 300 points.
3. It fetches all 49 forecast hours (0–48, hour 0 = departure hour) for those points in a few batched Open-Meteo calls and computes a risk level for every point and hour, using the same thresholds and load rules as the checkpoints.
4. The browser gets the whole grid in one response.
5. Moving the slider only changes which hour's values MapLibre's GPU heatmap layer reads. A truck marker on the selected route moves to where the truck is expected to be at that hour.

## Caching and limits

- Weather responses are cached by rounded coordinates and hour for 15–30 minutes, so re-planning the same trip or moving between routes doesn't refetch.
- Open-Meteo's free tier counts each location in a batch as one call (600/min, 10,000/day), so batches are chunked and cached.
- TomTom's free tier allows 2,500 requests/day; one trip plan uses three (two geocodes and one routing call).

## Frontend structure

| Folder | Contents |
|---|---|
| `src/api/` | Typed client for the two endpoints |
| `src/components/` | `PlanForm`, `RouteCards`, `MapView`, `HeatmapLayer`, `ForecastSlider`, `Legend` |
| `src/hooks/` | Data fetching and selected-route state |
| `src/types.ts` | Shared response types |
