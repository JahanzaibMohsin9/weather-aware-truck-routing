# Weather-Aware Truck Routing

A React + Django web app that helps a truck driver choose the safest route between two places, based on the forecast weather along each route, the truck's load weight and the travel time.

> **Status:** in development. Sections marked *TBD* are filled in as each part is built.

| | |
|---|---|
| Live app | *TBD* |
| Walkthrough (Loom) | *TBD* |

## What it does

The driver enters an origin, a destination, a departure date/time and the load weight in pounds. The app then:

1. Gets **3 route options** from a routing API.
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

*TBD once the backend and frontend are scaffolded.* The outline:

```bash
# backend
cd backend
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # macOS/Linux: cp; then add your TomTom key
python manage.py runserver
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

*TBD.* Backend tests cover every risk threshold boundary, the load rules, route ranking tie-breaks and checkpoint spacing. External APIs are mocked.

## Assumptions

These are choices where the brief leaves room for interpretation. Details are in [docs/risk-model.md](docs/risk-model.md).

- **Sampling interval:** the driver chooses 10, 25 or 50 miles; default is 25.
- **Range boundaries:** the brief's ranges touch (e.g. wind 25–34 and 35–44). A value belongs to the higher band once it reaches that band's lower bound, so 35.0 mph is High and 34.9 mph is Moderate. Rain and snow at exactly the top of Severe (1.00 in/hr, 3.0 in/hr) are Severe; above that is No Travel.
- **Wind** is the sustained 10 m wind speed, not gusts. Gusts are shown for information only.
- **Rain** is Open-Meteo's `rain + showers`, so convective storms count.
- **Weather at a checkpoint** uses the forecast hour covering the truck's ETA there.
- **ETAs** come from the routing API's travel times along the route and assume continuous driving, with no Hours-of-Service breaks.
- **No Travel routes:** the brief's ranking doesn't mention No Travel, so any route with a No Travel segment ranks after every route without one and is flagged as not recommended.
- **Forecast horizon:** checkpoints whose ETA is beyond the forecast range are shown as "no forecast", not as Low risk.
- **Heatmap time:** slider hour 0 is the departure hour.

## Known limitations

*Updated as the build progresses.*

- Free-tier hosting may sleep when idle, so the first request after a pause can be slow.
- Forecasts are hourly; conditions inside an hour are not modelled.
- No Hours-of-Service rest stops in ETAs (see Assumptions).
