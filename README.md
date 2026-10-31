# Weather-Aware Truck Routing

A React + Django web app that helps a truck driver choose the safest route between two places, based on the forecast weather along each route, the truck's load weight and the travel time.

| | |
|---|---|
| Live app | https://weather-aware-truck-routing-ccb92e0eafd6.herokuapp.com |
| Walkthrough (Loom) | *TBD* |

## What it does

The driver enters an origin, a destination, a departure date/time and the load weight in pounds. The app then:

1. Gets **3 distinct route options** from a routing API, running extra searches when the API returns fewer. If a trip genuinely has fewer distinct roads, the app shows the routes it found and says so.
2. Places a **checkpoint every 10, 25 or 50 miles** along each route (the driver picks the interval, default 25).
3. Works out the truck's **estimated arrival time** at each checkpoint and fetches the forecast for that place at that time.
4. Classifies each checkpoint as **Low, Moderate, High, Severe or No Travel** using the wind, rain and snow thresholds and the load-weight rules.
5. **Recommends a route**: fewest Severe miles, then fewest High miles, then lowest average risk, then shortest travel time.
6. Shows all routes, checkpoints, risk levels, ETAs and route summaries **on a map**, with a **weather heatmap along the trip corridor** and a **0–48 hour forecast slider**.

### On the map

- **Routes:** all three, with the selected one drawn wider and striped with the risk colour of each stretch of road. Click a route, its label or its card to select it.
- **Route summaries on the map:** a label on each route with distance and time, plus risk miles for the selected route. The recommended route is starred.
- **Checkpoints:** coloured by risk level. Click one for its ETA, wind, gusts, rain, snow, level and the rules that set the level.
- **Heatmap:** weather risk across a 30-mile corridor around the routes, for any hour from departure to +48 h. All 49 hours load once, so the slider (and its play button) never waits on the network.
- **Truck marker:** where the truck should be on the selected route at the slider's hour.
- **Side panel:** the recommendation and why, then the routes ranked best first, each with a bar showing how many miles fall at each risk level.

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
pip install -r requirements-dev.txt
copy .env.example .env          # macOS/Linux: cp; then add your TomTom key
python manage.py runserver
```

In development the frontend calls the API at `http://localhost:8000` (override with `VITE_API_BASE_URL`). In production Django serves the built frontend itself, so the page and the API share one origin.

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
| `DJANGO_SECRET_KEY` | backend | Django secret. Required when debug is off; the server refuses to start without it. |
| `DJANGO_DEBUG` | backend | `true` for local development only. Off when unset. |
| `ALLOWED_HOSTS` | backend | Extra hostnames to serve. On Heroku, `*.herokuapp.com` is allowed automatically. |
| `CORS_ALLOWED_ORIGINS` | backend | Local development only: the Vite dev server's URL |
| `VITE_API_BASE_URL` | frontend (build time) | Local development only: the backend's URL |

API keys stay on the backend; the browser never sees them.

## Deploying

The app deploys to [Heroku](https://www.heroku.com) as a single web dyno. The build compiles the React app, and Django (gunicorn + WhiteNoise) serves both the page and the API, so there is one URL and no CORS.

[![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://www.heroku.com/deploy?template=https://github.com/JahanzaibMohsin9/weather-aware-truck-routing)

1. Click the button, choose an app name, and paste your TomTom key. [`app.json`](app.json) sets everything else: the Node.js and Python buildpacks, a generated `DJANGO_SECRET_KEY`, and one Basic dyno.
2. To redeploy on every push, connect the app to this GitHub repository under **Deploy → GitHub** in the Heroku dashboard and turn on automatic deploys.

How the build works:

| File | Role |
|---|---|
| [`package.json`](package.json) | Heroku's Node.js buildpack runs `heroku-postbuild`, which builds `frontend/` into `frontend/dist` and removes its `node_modules` to keep the slug small |
| [`requirements.txt`](requirements.txt), [`.python-version`](.python-version) | The Python buildpack installs `backend/requirements.txt` on Python 3.12 |
| [`Procfile`](Procfile) | Runs gunicorn from `backend/` |

Heroku's router drops requests that take longer than 30 seconds. Each API request has a 25-second budget shared by all its calls to TomTom and Open-Meteo, so a slow provider gets a "please try again" message (HTTP 504) instead.

A Basic dyno doesn't sleep. On a sleeping (Eco) dyno the first request can take a few seconds; the page pings the API on load and says so if it's slow.

## Tests

```bash
cd backend
pytest
```

Tests use `config.test_settings`, so they need no `.env` file, API key or network access.

External APIs are mocked. The tests cover:

- **Risk rules:** every boundary in the wind, rain and snow table (e.g. 34.9 / 35 mph, 1.00 / 1.0001 in/hr), each load rule on both sides of its weight limit, worst-condition-wins, and that load rules never lower a level.
- **Ranking:** each tie-break in order, No Travel and missing-forecast routes ranking last, 0.821 beating 0.824 average risk even when much slower, and float noise falling through to travel time.
- **Mileage:** nearest-checkpoint attribution, including a No Travel reading at the destination.
- **Weather lookup:** which forecast hour is used for an ETA, rain + showers, beyond-forecast handling, batching and caching.
- **Heatmap:** corridor grid stays within 30 mi of the routes, covers the whole route, respects the point cap and is stable across overlapping trips; heat score is linear between thresholds and always rounds down to the level.
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
- **Forecast horizon:** departures must leave room for all 49 slider frames and the following precipitation timestamp inside the provider's 16 UTC calendar days. The cutoff is before 23:00 UTC on day 14 (today is day 1), and validation shows the exact date. Checkpoints beyond the forecast are shown as "No Forecast" and rank after fully covered routes. Missing heatmap data produces a visible warning for the selected hour.
- **Fewer than three routes:** some trips have only one sensible road (Key West → Marathon, for example). Refusing to plan them would hide the weather check the driver needs, so the app shows the routes that exist with a note. If an extra search failed rather than finding nothing new, the note says other routes may exist.
- **Heatmap time:** slider hour 0 is the departure hour (rounded down to the hour).
- **Displayed times** are in the viewer's time zone. The API returns UTC.
- **US only:** places are geocoded in the US. Including Canada made TomTom read state codes as street names ("Cheyenne, WY" became "Cheyenne Way, Ontario").
- **Place matching:** if TomTom's best match is only a fuzzy guess, the app says it couldn't find the place rather than planning a trip somewhere else. The matched place name is shown with the plan.

## Known limitations

*Updated as the build progresses.*

- The weather cache is in memory per worker, so it starts empty after each deploy or restart.
- Forecasts are hourly; conditions inside an hour are not modelled.
- No Hours-of-Service rest stops in ETAs (see Assumptions).
- Planning a long trip takes about 8–17 seconds, mostly TomTom computing truck alternatives. See [architecture](docs/architecture.md#where-the-time-goes).
- Routes found through a sideways via-point can include a short detour to reach that point.
- Canadian and Mexican places aren't supported.
