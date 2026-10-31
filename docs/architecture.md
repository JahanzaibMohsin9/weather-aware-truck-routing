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

In production one Heroku dyno runs everything: gunicorn serves the API, and WhiteNoise (inside Django) serves the built React app from `frontend/dist` at the site root. The page and the API share one origin, so no CORS is needed.

### Time budget

Heroku's router drops any request that takes longer than 30 seconds. Each API request gets a 25-second budget (`REQUEST_BUDGET_S` in `views.py`) that every outgoing call shares: a call gets at most the time left, and a retry happens only if enough time remains. When the budget runs out, the API answers 504 with a "please try again" message rather than letting the router cut the connection.

## Planning a trip (`POST /api/plan`)

1. **Validate** the request: origin and destination differ, load > 0, interval is 10, 25 or 50, departure is not in the past and leaves 48 hours plus a precipitation timestamp inside the provider's 16 UTC calendar days. The exclusive cutoff is UTC midnight today + 16 days - 49 hours.
2. **Geocode** origin and destination in parallel, US only. Weak fuzzy matches (TomTom match confidence below 0.85) are rejected rather than guessed. Results are cached for a day.
3. **Get routes** from TomTom in truck mode with the load weight, the departure time (so it uses historical traffic for that time of day) and two alternatives. If fewer than 3 distinct routes come back, the backend sends four top-up requests in parallel: the `shortest` and `eco` route types, and routes through a point pushed sideways from the main route on each side. Each top-up also requests two alternatives. It takes results in that priority order, dropping any route where more than 90% of either route lies on the other. A complete result has exactly three routes; otherwise the API explains that the comparison could not be completed. A failed optional search does not discard three valid routes from the other searches.
4. **Place checkpoints** by walking each route's polyline with haversine distance and dropping a point every N miles, plus the start and end.
5. **Estimate ETAs:** departure time plus the routing API's cumulative travel time at that point along the route. All times are UTC internally and shown in local time in the browser.
6. **Fetch weather** for all checkpoints in batched Open-Meteo requests and read the value for each checkpoint's ETA. If the weather API fails, the whole request fails rather than returning a plan with gaps.
7. **Classify** each checkpoint, assign each mile of road to its nearest checkpoint, and **rank** the routes (see [risk model](risk-model.md)).
8. **Respond** with routes, checkpoints, summaries, the recommended route and a one-line reason for the pick. Route geometry is simplified (Ramer–Douglas–Peucker, ~50 m) from about 10,000 points to about 500–1,500, so a 900-mile plan is about 60 KB.

### Where the time goes

A long trip takes about 8–17 seconds to plan, measured locally. Most of it is TomTom calculating truck routes with alternatives (about 2–6 s per call), plus one more round of routing calls when top-up is needed, and about 2–3 s for the weather batch. Geocoding and top-up requests run in parallel, and weather and geocoding are cached, so repeat plans are faster. The UI shows a loading state during this time.

## Heatmap (`POST /api/heatmap`)

The forecast slider has to feel instant, so the heatmap is built to need no network calls while the slider moves.

1. As soon as a plan arrives, the browser posts each route's checkpoints, the load weight and the departure time. Checkpoints 10–50 miles apart are precise enough to trace a 30-mile corridor, and sending them keeps the server stateless: no plan has to be stored between the two requests, which matters on hosting where each worker process has its own memory cache.
2. The backend lays a grid over the corridor and keeps the points within 30 miles of a route. The grid starts at 8-mile spacing and widens until there are at most 200 points, which caps weather API usage. It is aligned to fixed multiples of its spacing, so overlapping trips produce the same points and reuse cached forecasts.
3. It fetches the forecast for those points in batched Open-Meteo calls and computes, for every point and each hour from 0 to 48 (hour 0 = departure hour), the risk level and a continuous heat score, using the same thresholds and load rules as the checkpoints.
4. The browser gets everything in one gzip-compressed response, about 30 KB.
5. The browser builds one GeoJSON frame per hour once. Moving the slider only swaps which frame the heatmap source shows, so nothing is fetched or recomputed. The slider updates immediately, and the map follows through React's `useDeferredValue`, so a fast drag skips frames instead of lagging. A truck marker moves along the selected route to where the checkpoint ETAs put it at that hour.

### Drawing the heatmap

MapLibre's heatmap layer adds up overlapping Gaussian blobs, so on its own the colour would show how dense the points are, not how risky the weather is. To make the colour mean risk:

- Each point's weight is `score / 4`.
- The blob radius is 1.5 × the grid spacing, converted to pixels for the current zoom (MapLibre draws the world 512 px wide at zoom 0), so neighbouring points always overlap evenly.
- With that radius, a uniform grid of blobs adds up to about 0.62 × weight, so `heatmap-intensity` is set to 1.6 to bring the density back to about the weight.
- The colour ramp then uses the risk colours: green below 0.25 (Low), yellow at 0.25 (Moderate), orange at 0.5 (High), red at 0.75 (Severe), purple at 1 (No Travel).

The edges of the corridor fade naturally because they have fewer neighbours.

## Caching and limits

- Forecasts are cached per location (coordinates rounded to 0.01°, about 0.7 mi) for 30 minutes, so re-planning the same trip or nearby checkpoints don't refetch.
- Open-Meteo's free tier counts each location in a batch as one call (600/min, 10,000/day). Batches are chunked to 100 locations. A 900-mile trip at 25-mile spacing is about 110 locations for the plan, plus up to 200 for the heatmap, so roughly 30 new trips a day fit the free tier. Cached locations aren't fetched again.
- TomTom's free tier allows 2,500 requests/day. A plan uses 3 calls (two geocodes and one routing call) when TomTom returns 3 distinct routes, and 7 when top-up is needed. Cached geocodes bring that down.
- Calls to both providers are retried once after a short pause on rate limits, 5xx errors and network errors.

## Frontend structure

| Path | Contents |
|---|---|
| `src/api/client.ts` | Typed client for the endpoints; turns error responses into messages and per-field errors |
| `src/hooks/useRequest.ts` | One request at a time: a new request aborts the previous one, so a slow old response can't overwrite a newer one |
| `src/components/PlanForm.tsx` | Trip form with inline validation errors |
| `src/components/RouteCards.tsx` | Ranked route cards: badges, distance, time, arrival, risk miles, and a bar of miles per risk level |
| `src/components/MapView.tsx` | The map: routes, risk-coloured stripe on the selected route, checkpoints, route summary labels, heatmap, truck marker |
| `src/components/map/layers.ts` | Builds the GeoJSON and heatmap styling for the map |
| `src/components/CheckpointPopup.tsx` | Checkpoint details: ETA, wind, gusts, rain, snow, level and the rules that set it |
| `src/components/ForecastSlider.tsx` | 0–48 h slider with play/pause |
| `src/components/Legend.tsx` | Risk colours and heat scale; collapsed by default on phones |
| `src/utils/` | Formatting and route geometry helpers (position along a route by mile or by time) |
| `src/maplibreSetup.ts` | Points MapLibre at its web worker; Vite's bundling otherwise breaks the worker URL |

Times are shown in the viewer's own time zone.

On screens narrower than 900 px the map takes the top half and the panel scrolls below it.
