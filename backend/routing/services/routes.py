"""Find three distinct truck routes, topping up when the API returns fewer.

TomTom's own alternatives come first. If there are fewer than three distinct
routes, we ask for other route types, then for routes forced through a point
pushed sideways from the main route. Near-duplicates are dropped at each step.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..domain.geo import (
    LatLng,
    TimeProfile,
    bearing_deg,
    cumulative_miles,
    haversine_mi,
    offset_point,
    point_at_mile,
    shared_fraction,
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


@dataclass(frozen=True)
class PlannedRoute:
    points: list[LatLng]
    distance_mi: float
    duration_s: float
    profile: TimeProfile
    source: str  # how it was found: "fastest", "alternative", "shortest", "eco", "via"


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
    return PlannedRoute(raw.points, total, raw.travel_time_s, profile, source)


def is_duplicate(candidate: PlannedRoute, existing: list[PlannedRoute]) -> bool:
    return any(
        shared_fraction(candidate.points, r.points) > DUPLICATE_SHARE
        or shared_fraction(r.points, candidate.points) > DUPLICATE_SHARE
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

    for route_type in EXTRA_ROUTE_TYPES:
        if len(routes) >= WANTED_ROUTES:
            break
        try:
            add(client.calculate_routes([origin, destination], route_type=route_type, **common), route_type)
        except NoRouteFound:
            continue

    if len(routes) < WANTED_ROUTES:
        main = routes[0]
        midpoint = point_at_mile(main.points, cumulative_miles(main.points), main.distance_mi / 2)
        heading = bearing_deg(origin, destination)
        offset = max(MIN_VIA_OFFSET_MI, VIA_OFFSET_FRACTION * haversine_mi(origin, destination))
        for side in (90, -90):
            if len(routes) >= WANTED_ROUTES:
                break
            via = offset_point(midpoint, heading + side, offset)
            try:
                add(client.calculate_routes([origin, via, destination], **common), "via")
            except NoRouteFound:  # e.g. the via point landed in a lake
                continue

    notes = []
    if len(routes) < WANTED_ROUTES:
        notes.append(
            f"Only {len(routes)} distinct route(s) exist for this trip; "
            "other options were more than 90% the same road as an existing route."
        )
    return routes, notes
