# Weather-Aware Truck Routing

A React + Django web app that helps a truck driver choose the safest route between two places, based on the forecast weather along each route, the truck's load weight and the travel time.

> **Status:** in development. Sections marked *TBD* are filled in as each part is built.

| | |
|---|---|
| Live app | *TBD* |
| Walkthrough (Loom) | *TBD* |

## What it does

The driver enters an origin, a destination, a departure date/time and the load weight in pounds. The app then:

1. Gets **3 route options** from a routing API, topping up with extra requests when the API returns fewer.
2. Places a **checkpoint every 10, 25 or 50 miles** along each route (the driver picks the interval, default 25).
3. Works out the truck's **estimated arrival time** at each checkpoint and fetches the forecast for that place at that time.
4. Classifies each checkpoint as **Low, Moderate, High, Severe or No Travel** using the wind, rain and snow thresholds and the load-weight rules.
5. **Recommends a route**: fewest Severe miles, then fewest High miles, then lowest average risk, then shortest travel time.
6. Shows all routes, checkpoints, risk levels, ETAs and route summaries **on a map**, with a **weather heatmap along the trip corridor** and a **0–48 hour forecast slider**.

## Tech stack

| Part | Choice |
|---|---|
| Backend | Python 3.12, Django 5, Django REST Framework |
| Frontend | React, TypeScript, Vite, MUI |
| Map | MapLibre GL JS (`react-map-gl`) |
| Routing and geocoding | TomTom Routing and Search APIs (truck mode, alternative routes) |
| Weather | Open-Meteo forecast API (hourly, no key needed) |

## Documentation

- [Architecture](docs/architecture.md): components, request flow and how the heatmap stays smooth
- [Risk model](docs/risk-model.md): thresholds, boundary handling, load rules and route ranking
- [API](docs/api.md): backend endpoints and payloads

## Running locally

Requires Python 3.12 and Node 20+. Get a free TomTom key at developer.tomtom.com.

```bash
# backend
cd backend
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # macOS/Linux: cp; then add your TomTom key
python manage.py runserver
```

To check routing on a real trip without the UI:

```bash
python manage.py check_routes "Dallas, TX" "Denver, CO" --load 36000 --interval 25
```

```bash
# frontend
cd frontend
npm install
npm run dev
```

### Environment variables

| Variable | Where | Purpose |
|---|---|---|
| `TOMTOM_API_KEY` | backend | Routing and geocoding |
| `DJANGO_SECRET_KEY` | backend | Django secret |
| `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` | backend | Deployment hosts |
| `VITE_API_BASE_URL` | frontend | Backend URL |

API keys stay on the backend; the browser never sees them.

## Tests

```bash
cd backend
pytest
```

External APIs are mocked, so tests need no key or network. They cover:

- **Risk rules:** every boundary in the wind, rain and snow table (e.g. 34.9 / 35 mph, 1.00 / 1.0001 in/hr), each load rule on both sides of its weight limit, worst-condition-wins, and that load rules never lower a level.
- **Ranking:** each tie-break in order, No Travel and missing-forecast routes ranking last, 0.821 beating 0.824 average risk even when much slower, and float noise falling through to travel time.
- **Mileage:** nearest-checkpoint attribution, including a No Travel reading at the destination.
- **Weather lookup:** which forecast hour is used for an ETA, rain + showers, beyond-forecast handling, batching and caching.
- **Routing:** checkpoint spacing, ETAs from TomTom's per-point times, overlap detection, topping up to three routes, retries, and rejecting weak geocode matches.
- **API:** input validation and how provider errors map to HTTP status codes.

## Assumptions

These are choices where the brief leaves room for interpretation. Details are in [docs/risk-model.md](docs/risk-model.md).

- **Sampling interval:** the driver chooses 10, 25 or 50 miles; default is 25.
- **Range boundaries:** the brief's ranges touch (e.g. wind 25–34 and 35–44). A value belongs to the higher band once it reaches that band's lower bound, so 35.0 mph is High and 34.9 mph is Moderate. Rain and snow at exactly the top of Severe (1.00 in/hr, 3.0 in/hr) are Severe; above that is No Travel.
- **Wind** is the sustained 10 m wind speed, not gusts. Gusts are shown for information only.
- **Rain** is Open-Meteo's `rain + showers`, so convective storms count.
- **Weather at a checkpoint** uses the forecast hour covering the truck's ETA there.
- **Miles per checkpoint:** each mile of road takes the level of its nearest checkpoint, so the origin and destination count too.
- **ETAs** come from the routing API's travel times along the route and assume continuous driving, with no Hours-of-Service breaks.
- **Ranking order:** risk comes before travel time, following the brief's preference list. Values are compared unrounded; rounding is for display only.
- **No Travel routes:** the brief's ranking doesn't mention No Travel, so any route with a No Travel checkpoint ranks after every route without one and is flagged as not recommended.
- **Forecast horizon:** departures can be up to 14 days ahead. Checkpoints whose ETA is still beyond the forecast are shown as "No Forecast", not as Low risk, and a route with such gaps ranks after fully covered routes.
- **Heatmap time:** slider hour 0 is the departure hour.
- **US only:** places are geocoded in the US. Including Canada made TomTom read state codes as street names ("Cheyenne, WY" became "Cheyenne Way, Ontario").
- **Place matching:** if TomTom's best match is only a fuzzy guess, the app says it couldn't find the place rather than planning a trip somewhere else. The matched place name is shown with the plan.

## Known limitations

*Updated as the build progresses.*

- Free-tier hosting may sleep when idle, so the first request after a pause can be slow.
- Forecasts are hourly; conditions inside an hour are not modelled.
- No Hours-of-Service rest stops in ETAs (see Assumptions).
- Planning a long trip takes about 8–17 seconds, mostly TomTom computing truck alternatives. See [architecture](docs/architecture.md#where-the-time-goes).
- Routes found through a sideways via-point can include a short detour to reach that point.
- Canadian and Mexican places aren't supported.
