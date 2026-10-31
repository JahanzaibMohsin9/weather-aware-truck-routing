"""Pure geometry: distances, walking a polyline, checkpoints and ETAs.

Points are (lat, lng) tuples in degrees. Distances are statute miles.
Nothing here does I/O, so it can be tested without the network.
"""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Sequence

EARTH_RADIUS_MI = 3958.7613
MILES_PER_DEGREE_LAT = math.pi * EARTH_RADIUS_MI / 180

LatLng = tuple[float, float]


def haversine_mi(a: LatLng, b: LatLng) -> float:
    """Great-circle distance between two points."""
    lat1, lng1 = map(math.radians, a)
    lat2, lng2 = map(math.radians, b)
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_MI * math.asin(min(1.0, math.sqrt(h)))


def bearing_deg(a: LatLng, b: LatLng) -> float:
    """Initial compass bearing from a to b (0 = north, 90 = east)."""
    lat1, lng1 = map(math.radians, a)
    lat2, lng2 = map(math.radians, b)
    dlng = lng2 - lng1
    x = math.sin(dlng) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlng)
    return math.degrees(math.atan2(x, y)) % 360


def offset_point(origin: LatLng, bearing: float, distance_mi: float) -> LatLng:
    """The point `distance_mi` from `origin` along compass `bearing`."""
    lat1, lng1 = map(math.radians, origin)
    theta = math.radians(bearing)
    delta = distance_mi / EARTH_RADIUS_MI
    lat2 = math.asin(
        math.sin(lat1) * math.cos(delta) + math.cos(lat1) * math.sin(delta) * math.cos(theta)
    )
    lng2 = lng1 + math.atan2(
        math.sin(theta) * math.sin(delta) * math.cos(lat1),
        math.cos(delta) - math.sin(lat1) * math.sin(lat2),
    )
    return math.degrees(lat2), (math.degrees(lng2) + 540) % 360 - 180


def cumulative_miles(points: Sequence[LatLng]) -> list[float]:
    """Distance from the first point to each point along the polyline."""
    if not points:
        return []
    out = [0.0]
    for prev, cur in zip(points, points[1:]):
        out.append(out[-1] + haversine_mi(prev, cur))
    return out


def point_at_mile(points: Sequence[LatLng], cum: Sequence[float], mile: float) -> LatLng:
    """Position `mile` miles along the polyline (`cum` from `cumulative_miles`)."""
    if mile <= 0:
        return points[0]
    if mile >= cum[-1]:
        return points[-1]
    i = bisect.bisect_right(cum, mile)  # cum[i-1] <= mile < cum[i]
    t = (mile - cum[i - 1]) / (cum[i] - cum[i - 1])
    (lat1, lng1), (lat2, lng2) = points[i - 1], points[i]
    return lat1 + t * (lat2 - lat1), lng1 + t * (lng2 - lng1)


def resample(points: Sequence[LatLng], step_mi: float) -> list[LatLng]:
    """Points every `step_mi` along the polyline, including both ends."""
    cum = cumulative_miles(points)
    total = cum[-1]
    count = max(1, math.ceil(total / step_mi - 1e-9))  # 10.0000000001 / 1 is 10 steps
    return [point_at_mile(points, cum, total * k / count) for k in range(count + 1)]


def simplify(points: Sequence[LatLng], tolerance_deg: float) -> list[LatLng]:
    """Ramer-Douglas-Peucker: drop points that sit within `tolerance_deg` of
    the line through their neighbours. Used to shrink geometry for the map."""
    if len(points) < 3:
        return list(points)
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        first, last = stack.pop()
        (ay, ax), (by, bx) = points[first], points[last]
        dx, dy = bx - ax, by - ay
        length = math.hypot(dx, dy)
        worst, worst_i = 0.0, -1
        for i in range(first + 1, last):
            py, px = points[i]
            if length == 0:
                d = math.hypot(px - ax, py - ay)
            else:
                d = abs(dy * (px - ax) - dx * (py - ay)) / length
            if d > worst:
                worst, worst_i = d, i
        if worst > tolerance_deg:
            keep[worst_i] = True
            stack += [(first, worst_i), (worst_i, last)]
    return [p for p, k in zip(points, keep) if k]


@dataclass(frozen=True)
class TimeProfile:
    """Cumulative travel time (seconds) against distance along a route (miles).

    Built from the knots the routing API reports, linear in between. When the
    API gives no per-point times, `proportional` spreads the total evenly.
    """

    miles: tuple[float, ...]
    seconds: tuple[float, ...]

    @classmethod
    def proportional(cls, total_miles: float, total_seconds: float) -> TimeProfile:
        return cls((0.0, total_miles), (0.0, total_seconds))

    @classmethod
    def from_knots(cls, knots: Sequence[tuple[float, float]]) -> TimeProfile:
        """Knots are (mile, seconds) pairs; (0, 0) is added if missing."""
        ordered = sorted(set(knots))
        if not ordered or ordered[0] != (0.0, 0.0):
            ordered.insert(0, (0.0, 0.0))
        miles = [m for m, _ in ordered]
        seconds = [s for _, s in ordered]
        if any(b < a for a, b in zip(seconds, seconds[1:])):
            raise ValueError("travel time must not decrease along the route")
        return cls(tuple(miles), tuple(seconds))

    def seconds_at(self, mile: float) -> float:
        if mile <= self.miles[0]:
            return self.seconds[0]
        if mile >= self.miles[-1]:
            return self.seconds[-1]
        i = bisect.bisect_right(self.miles, mile)
        m0, m1 = self.miles[i - 1], self.miles[i]
        s0, s1 = self.seconds[i - 1], self.seconds[i]
        return s0 + (s1 - s0) * (mile - m0) / (m1 - m0)


@dataclass(frozen=True)
class Checkpoint:
    mile: float
    lat: float
    lng: float
    eta: datetime


# Interval checkpoints closer than this to the destination are dropped, so
# float noise never creates a near-duplicate of the destination checkpoint.
_END_TOLERANCE_MI = 1e-6


def checkpoint_miles(total_miles: float, interval_mi: float) -> list[float]:
    """Origin, every `interval_mi`, and the destination."""
    if interval_mi <= 0:
        raise ValueError("interval must be positive")
    miles = []
    k = 0
    while k * interval_mi < total_miles - _END_TOLERANCE_MI:
        miles.append(k * interval_mi)
        k += 1
    miles.append(total_miles)
    return miles


def build_checkpoints(
    points: Sequence[LatLng],
    interval_mi: float,
    profile: TimeProfile,
    departure: datetime,
) -> list[Checkpoint]:
    """Checkpoints along the route with the truck's ETA at each one."""
    cum = cumulative_miles(points)
    checkpoints = []
    for mile in checkpoint_miles(cum[-1], interval_mi):
        lat, lng = point_at_mile(points, cum, mile)
        eta = departure + timedelta(seconds=profile.seconds_at(mile))
        checkpoints.append(Checkpoint(mile=mile, lat=lat, lng=lng, eta=eta))
    return checkpoints


def coverage_miles(miles: Sequence[float]) -> list[float]:
    """Miles of road each checkpoint stands for: everything nearer to it than
    to any other checkpoint. Lengths add up to the route distance."""
    if len(miles) < 2:
        return [0.0] * len(miles)
    bounds = [miles[0], *((a + b) / 2 for a, b in zip(miles, miles[1:])), miles[-1]]
    return [hi - lo for lo, hi in zip(bounds, bounds[1:])]


OVERLAP_TOLERANCE_MI = 0.3


def overlap_samples(points: Sequence[LatLng]) -> list[LatLng]:
    """Evenly spaced points for `shared_fraction_of_samples`, so long straight
    segments with few vertices can't hide overlap. Compute once per route."""
    return resample(points, OVERLAP_TOLERANCE_MI)


def shared_fraction(a: Sequence[LatLng], b: Sequence[LatLng]) -> float:
    """Fraction of route `a`'s length lying within ~0.3 mi of route `b`."""
    return shared_fraction_of_samples(overlap_samples(a), overlap_samples(b))


def shared_fraction_of_samples(samples_a: Sequence[LatLng], samples_b: Sequence[LatLng]) -> float:
    """`shared_fraction` on routes already passed through `overlap_samples`.

    `b`'s samples go into a grid so each lookup checks only nearby cells.
    """
    # Every point on b is within half a step of one of its samples.
    threshold = OVERLAP_TOLERANCE_MI * 1.5

    max_lat = max(abs(lat) for lat, _ in [*samples_a, *samples_b])
    cell_lat = threshold / MILES_PER_DEGREE_LAT
    cell_lng = threshold / (MILES_PER_DEGREE_LAT * math.cos(math.radians(min(max_lat, 89))))

    def cell(p: LatLng) -> tuple[int, int]:
        return math.floor(p[0] / cell_lat), math.floor(p[1] / cell_lng)

    grid: dict[tuple[int, int], list[LatLng]] = {}
    for p in samples_b:
        grid.setdefault(cell(p), []).append(p)

    def near_b(p: LatLng) -> bool:
        ci, cj = cell(p)
        return any(
            haversine_mi(p, q) <= threshold
            for di in (-1, 0, 1)
            for dj in (-1, 0, 1)
            for q in grid.get((ci + di, cj + dj), ())
        )

    return sum(near_b(p) for p in samples_a) / len(samples_a)
