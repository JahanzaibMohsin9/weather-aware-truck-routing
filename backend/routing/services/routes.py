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
from typing import Callable

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
from .errors import NoRouteFound, ProviderError
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
    progress: Callable[[str, str], None] | None = None,
) -> tuple[list[PlannedRoute], list[str]]:
    """Up to three distinct routes, plus notes for the driver.

    Fewer than three is a valid answer (some trips have only one sensible
    road); the notes say so, and say whether a failed search might have hidden
    another route.
    """
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
    if not routes:
        raise NoRouteFound("No truck routes returned")

    failed_searches = 0
    if len(routes) < WANTED_ROUTES:
        if progress:
            found = f"{len(routes)} distinct route{'s' if len(routes) != 1 else ''}"
            progress("alternatives", f"TomTom returned {found}; searching for alternatives")
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

        def fetch(kwargs: dict) -> tuple[list[RawRoute], ProviderError | None]:
            try:
                return client.calculate_routes(max_alternatives=WANTED_ROUTES - 1, **kwargs, **common), None
            except NoRouteFound:  # e.g. a via point that landed in a lake
                return [], None
            except ProviderError as exc:
                # An optional search failing must not discard the routes we have.
                return [], exc

        with ThreadPoolExecutor(max_workers=len(extra)) as pool:
            results = list(pool.map(fetch, [kwargs for _, kwargs in extra]))
        for (source, _), (raws, _) in zip(extra, results):  # priority order, not completion order
            add(raws, source)
        failed_searches = sum(error is not None for _, error in results)

    notes = []
    if len(routes) < WANTED_ROUTES:
        found = f"{len(routes)} distinct truck route{'s' if len(routes) != 1 else ''}"
        if failed_searches:
            notes.append(
                f"Showing {found}. Some searches for alternatives failed, so other routes may exist; "
                "try again for a fuller comparison."
            )
        else:
            notes.append(
                f"Only {found} for this trip: every other option found was more than 90% the same road."
            )
    return routes, notes
