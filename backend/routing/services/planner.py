"""Plan a trip: geocode, find routes, place checkpoints, fetch weather, score
each checkpoint, rank the routes and shape the API response."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ..domain.geo import Checkpoint, build_checkpoints, coverage_miles, haversine_mi, simplify
from ..domain.levels import NO_FORECAST
from ..domain.recommend import RouteSummary, rank, recommend, summarize
from ..domain.risk import Assessment, assess
from .errors import InvalidTrip
from .routes import PlannedRoute, find_routes
from .tomtom import TomTomClient
from .weather import OpenMeteoClient, Weather, weather_at

ROUTE_IDS = "ABC"
# ~50 m: invisible at map zoom levels, cuts a route from ~10,000 points to ~1,000.
GEOMETRY_TOLERANCE_DEG = 0.0005
SAME_PLACE_MI = 1.0


@dataclass(frozen=True)
class PlanRequest:
    origin: str
    destination: str
    departure: datetime
    load_lbs: float
    interval_miles: int


def plan_trip(
    req: PlanRequest,
    *,
    tomtom: TomTomClient,
    weather: OpenMeteoClient,
    now: datetime | None = None,
) -> dict:
    now = now or datetime.now(timezone.utc)
    with ThreadPoolExecutor(max_workers=2) as pool:
        origin, destination = pool.map(tomtom.geocode, [req.origin, req.destination])
    if haversine_mi(origin.point, destination.point) < SAME_PLACE_MI:
        raise InvalidTrip("Origin and destination are the same place.")

    # TomTom rejects departure times in the past; ETAs still use the user's time.
    depart_at = max(req.departure, now + timedelta(minutes=1))
    routes, notes = find_routes(
        tomtom, origin.point, destination.point, load_lbs=req.load_lbs, depart_at=depart_at
    )

    checkpoints = [
        build_checkpoints(r.points, req.interval_miles, r.profile, req.departure) for r in routes
    ]
    # One batched weather lookup for every checkpoint on every route.
    series = iter(weather.series_for([(cp.lat, cp.lng) for cps in checkpoints for cp in cps]))
    conditions = [[weather_at(next(series), cp.eta) for cp in cps] for cps in checkpoints]

    assessments = [
        [
            None if w is None else assess(
                wind_mph=w.wind_mph, rain_in_hr=w.rain_in_hr, snow_in_hr=w.snow_in_hr, load_lbs=req.load_lbs
            )
            for w in route_conditions
        ]
        for route_conditions in conditions
    ]
    summaries = [
        summarize([cp.mile for cp in cps], [a.level if a else None for a in route_assessments], r.duration_s)
        for r, cps, route_assessments in zip(routes, checkpoints, assessments)
    ]

    ids = list(ROUTE_IDS[: len(routes)])
    recommended, explanation = recommend(summaries, ids)
    order = rank(summaries)
    notes += [
        f"The forecast ends before Route {ids[i]} does; its last "
        f"{s.no_forecast_mi:.0f} mi are shown without weather."
        for i, s in enumerate(summaries)
        if not s.forecast_complete
    ]

    return {
        "origin": _place(origin),
        "destination": _place(destination),
        "departure": _iso(req.departure),
        "load_lbs": req.load_lbs,
        "interval_miles": req.interval_miles,
        "routes": [
            _route(ids[i], order.index(i) + 1, i == recommended, routes[i], summaries[i],
                   checkpoints[i], conditions[i], assessments[i])
            for i in range(len(routes))
        ],
        "recommended_route_id": None if recommended is None else ids[recommended],
        "explanation": explanation,
        "notes": notes,
    }


def _route(
    route_id: str,
    position: int,
    recommended: bool,
    route: PlannedRoute,
    summary: RouteSummary,
    checkpoints: list[Checkpoint],
    conditions: list[Weather | None],
    assessments: list[Assessment | None],
) -> dict:
    geometry = simplify(route.points, GEOMETRY_TOLERANCE_DEG)
    covers = coverage_miles([cp.mile for cp in checkpoints])
    return {
        "id": route_id,
        "rank": position,
        "recommended": recommended,
        "source": route.source,
        "geometry": [[lng, lat] for lat, lng in geometry],
        "distance_mi": route.distance_mi,
        "duration_min": route.duration_s / 60,
        "summary": {
            "no_travel_mi": summary.no_travel_mi,
            "severe_mi": summary.severe_mi,
            "high_mi": summary.high_mi,
            "no_forecast_mi": summary.no_forecast_mi,
            "avg_risk": summary.avg_risk,
            "has_no_travel": summary.has_no_travel,
            "forecast_complete": summary.forecast_complete,
        },
        "checkpoints": [
            _checkpoint(cp, covered, w, a)
            for cp, covered, w, a in zip(checkpoints, covers, conditions, assessments)
        ],
    }


def _checkpoint(cp: Checkpoint, covered: float, w: Weather | None, a: Assessment | None) -> dict:
    return {
        "mile": cp.mile,
        "covers_mi": covered,
        "lat": cp.lat,
        "lng": cp.lng,
        "eta": _iso(cp.eta),
        "wind_mph": w.wind_mph if w else None,
        "gust_mph": w.gust_mph if w else None,
        "rain_in_hr": w.rain_in_hr if w else None,
        "snow_in_hr": w.snow_in_hr if w else None,
        "level": a.level.label if a else NO_FORECAST,
        "level_value": int(a.level) if a else None,
        "reasons": a.reasons if a else [],
    }


def _place(place) -> dict:
    return {"label": place.label, "lat": place.lat, "lng": place.lng}


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

