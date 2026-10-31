"""Find three distinct truck routes, topping up when the API returns fewer.

TomTom's own alternatives come first. If there are fewer than three distinct
routes, we ask for other route types and for routes forced through a point
pushed sideways from the main route. Those requests run in parallel, and
their results are considered in a fixed priority order, dropping
near-duplicates.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime

from ..domain.geo import (
    LatLng,
    TimeProfile,
    bearing_deg,
    cumulative_miles,
    haversine_mi,
    offset_point,
    overlap_samples,
    point_at_mile,
    shared_fraction_of_samples,
)
from .errors import NoRouteFound
from .tomtom import RawRoute, TomTomClient

WANTED_ROUTES = 3
# Two routes are the same route if more than this fraction of either one lies
# on the other. Checking both ways also rejects a route that is an existing
# route plus a detour (all of the existing route lies on it).
DUPLICATE_SHARE = 0.9
# Sideways via-point distance, as a fraction of the straight-line trip length.
VIA_OFFSET_FRACTION = 0.1
MIN_VIA_OFFSET_MI = 10.0
EXTRA_ROUTE_TYPES = ("shortest", "eco")
VIA_SIDES = (90, -90)


@dataclass(frozen=True)
class PlannedRoute:
    points: list[LatLng]
    distance_mi: float
    duration_s: float
    profile: TimeProfile
    source: str  # how it was found: "fastest", "alternative", "shortest", "eco", "via"
    samples: list[LatLng] = field(repr=False)  # for overlap checks


def to_planned(raw: RawRoute, source: str) -> PlannedRoute:
    """Convert a TomTom route, mapping its per-point times onto our distances."""
    cum = cumulative_miles(raw.points)
    total = cum[-1]
    knots = [(cum[i], t) for i, t in raw.progress if 0 <= i < len(cum)]
    if knots:
        knots.append((total, raw.travel_time_s))
        profile = TimeProfile.from_knots(knots)
    else:
        profile = TimeProfile.proportional(total, raw.travel_time_s)
    return PlannedRoute(raw.points, total, raw.travel_time_s, profile, source, overlap_samples(raw.points))


def is_duplicate(candidate: PlannedRoute, existing: list[PlannedRoute]) -> bool:
    return any(
        shared_fraction_of_samples(candidate.samples, r.samples) > DUPLICATE_SHARE
        or shared_fraction_of_samples(r.samples, candidate.samples) > DUPLICATE_SHARE
        for r in existing
    )


def find_routes(
    client: TomTomClient,
    origin: LatLng,
    destination: LatLng,
    *,
    load_lbs: float,
    depart_at: datetime,
) -> tuple[list[PlannedRoute], list[str]]:
    """Up to three distinct routes, plus notes for the driver."""
    common = {"load_lbs": load_lbs, "depart_at": depart_at}
    routes: list[PlannedRoute] = []

    def add(raws: list[RawRoute], source: str) -> None:
        for raw in raws:
            if len(routes) >= WANTED_ROUTES:
                return
            candidate = to_planned(raw, source)
            if not is_duplicate(candidate, routes):
                routes.append(candidate)

    first = client.calculate_routes(
        [origin, destination], max_alternatives=WANTED_ROUTES - 1, **common
    )
    add(first[:1], "fastest")
    add(first[1:], "alternative")

    if len(routes) < WANTED_ROUTES:
        main = routes[0]
        midpoint = point_at_mile(main.points, cumulative_miles(main.points), main.distance_mi / 2)
        heading = bearing_deg(origin, destination)
        offset = max(MIN_VIA_OFFSET_MI, VIA_OFFSET_FRACTION * haversine_mi(origin, destination))
        extra = [
            (route_type, {"locations": [origin, destination], "route_type": route_type})
            for route_type in EXTRA_ROUTE_TYPES
        ] + [
            ("via", {"locations": [origin, offset_point(midpoint, heading + side, offset), destination]})
            for side in VIA_SIDES
        ]

        def fetch(kwargs: dict) -> list[RawRoute]:
            try:
                return client.calculate_routes(**kwargs, **common)
            except NoRouteFound:  # e.g. a via point that landed in a lake
                return []

        with ThreadPoolExecutor(max_workers=len(extra)) as pool:
            results = list(pool.map(fetch, [kwargs for _, kwargs in extra]))
        for (source, _), raws in zip(extra, results):  # priority order, not completion order
            add(raws, source)

    notes = []
    if len(routes) < WANTED_ROUTES:
        notes.append(
            f"Only {len(routes)} distinct route(s) exist for this trip; "
            "other options were more than 90% the same road as an existing route."
        )
    return routes, notes
