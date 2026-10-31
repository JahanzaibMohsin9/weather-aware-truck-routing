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
2. **Geocode** origin and destination in parallel, US only. Weak fuzzy matches (TomTom match confidence below 0.85) are rejected rather than guessed. Results are cached for a day.
3. **Get routes** from TomTom in truck mode with the load weight, the departure time (so it uses historical traffic for that time of day) and two alternatives. If fewer than 3 distinct routes come back, the backend sends four top-up requests in parallel: the `shortest` and `eco` route types, and routes through a point pushed sideways from the main route on each side. It then takes them in that priority order, dropping any route where more than 90% of either route lies on the other. Only when no distinct third route exists does it return fewer, and the response says so; the app doesn't make routes up.
4. **Place checkpoints** by walking each route's polyline with haversine distance and dropping a point every N miles, plus the start and end.
5. **Estimate ETAs:** departure time plus the routing API's cumulative travel time at that point along the route. All times are UTC internally and shown in local time in the browser.
6. **Fetch weather** for all checkpoints in batched Open-Meteo requests and read the value for each checkpoint's ETA. If the weather API fails, the whole request fails rather than returning a plan with gaps.
7. **Classify** each checkpoint, assign each mile of road to its nearest checkpoint, and **rank** the routes (see [risk model](risk-model.md)).
8. **Respond** with routes, checkpoints, summaries, the recommended route and a one-line reason for the pick. Route geometry is simplified (Ramer–Douglas–Peucker, ~50 m) from about 10,000 points to about 500–1,500, so a 900-mile plan is about 60 KB.

### Where the time goes

A long trip takes about 8–17 seconds to plan, measured locally. Most of it is TomTom calculating truck routes with alternatives (about 2–6 s per call), plus one more round of routing calls when top-up is needed, and about 2–3 s for the weather batch. Geocoding and top-up requests run in parallel, and weather and geocoding are cached, so repeat plans are faster. The UI shows a loading state during this time.

## Heatmap (`POST /api/heatmap`)

The forecast slider has to feel instant, so the heatmap is built to need no network calls while the slider moves.

1. The browser posts each route's checkpoints, the load weight and the departure hour. Checkpoints 10–50 miles apart are precise enough to trace a 30-mile corridor, and sending them keeps the server stateless: no plan has to be stored between the two requests, which matters on hosting where each worker process has its own memory cache.
2. The backend builds a grid of points over the checkpoints' bounding box and keeps only points within about 30 miles of a route (the trip corridor), up to roughly 300 points.
3. It fetches all 49 forecast hours (0–48, hour 0 = departure hour) for those points in a few batched Open-Meteo calls and computes a risk level for every point and hour, using the same thresholds and load rules as the checkpoints.
4. The browser gets the whole grid in one response.
5. Moving the slider only changes which hour's values MapLibre's GPU heatmap layer reads. A truck marker on the selected route moves to where the truck is expected to be at that hour.

## Caching and limits

- Forecasts are cached per location (coordinates rounded to 0.01°, about 0.7 mi) for 30 minutes, so re-planning the same trip or nearby checkpoints don't refetch.
- Open-Meteo's free tier counts each location in a batch as one call (600/min, 10,000/day). Batches are chunked to 100 locations; a 900-mile trip at 25-mile spacing is about 110 locations.
- TomTom's free tier allows 2,500 requests/day. A plan uses 3 calls (two geocodes and one routing call) when TomTom returns 3 distinct routes, and 7 when top-up is needed. Cached geocodes bring that down.
- Calls to both providers are retried once after a short pause on rate limits, 5xx errors and network errors.

## Frontend structure

| Folder | Contents |
|---|---|
| `src/api/` | Typed client for the two endpoints |
| `src/components/` | `PlanForm`, `RouteCards`, `MapView`, `HeatmapLayer`, `ForecastSlider`, `Legend` |
| `src/hooks/` | Data fetching and selected-route state |
| `src/types.ts` | Shared response types |
