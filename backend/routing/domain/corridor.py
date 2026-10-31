"""Grid of weather sample points covering the trip corridor.

The grid is aligned to fixed multiples of its spacing, so the same area gives
the same points on every request and their forecasts can be cached. Spacing
grows until the corridor fits in `max_points`, which bounds weather API usage.
"""

from __future__ import annotations

import math
from typing import Sequence

from .geo import MILES_PER_DEGREE_LAT, LatLng, haversine_mi, resample

CORRIDOR_MI = 30.0
MAX_POINTS = 200
MIN_SPACING_MI = 8.0
SPACING_GROWTH = 1.2
_ROUTE_SAMPLE_MI = 5.0


def corridor_grid(
    routes: Sequence[Sequence[LatLng]],
    corridor_mi: float = CORRIDOR_MI,
    max_points: int = MAX_POINTS,
) -> tuple[list[LatLng], float]:
    """Grid points within `corridor_mi` of any route, and the spacing used (miles)."""
    samples = [p for route in routes if len(route) >= 2 for p in resample(route, _ROUTE_SAMPLE_MI)]
    samples += [route[0] for route in routes if len(route) == 1]
    if not samples:
        return [], MIN_SPACING_MI

    near = _NearRoute(samples, corridor_mi)
    lats = [lat for lat, _ in samples]
    lngs = [lng for _, lng in samples]
    # One fixed reference latitude per area keeps the grid stable across requests.
    ref_lat = round((min(lats) + max(lats)) / 2)
    pad_lat = corridor_mi / MILES_PER_DEGREE_LAT
    pad_lng = corridor_mi / (MILES_PER_DEGREE_LAT * math.cos(math.radians(ref_lat)))
    bounds = (min(lats) - pad_lat, max(lats) + pad_lat, min(lngs) - pad_lng, max(lngs) + pad_lng)

    spacing = MIN_SPACING_MI
    while True:
        points = [p for p in _grid(bounds, spacing, ref_lat) if near(p)]
        if len(points) <= max_points:
            return points, spacing
        spacing *= SPACING_GROWTH


def _grid(bounds, spacing_mi: float, ref_lat: float):
    min_lat, max_lat, min_lng, max_lng = bounds
    step_lat = spacing_mi / MILES_PER_DEGREE_LAT
    step_lng = spacing_mi / (MILES_PER_DEGREE_LAT * math.cos(math.radians(ref_lat)))
    for i in range(math.ceil(min_lat / step_lat), math.floor(max_lat / step_lat) + 1):
        for j in range(math.ceil(min_lng / step_lng), math.floor(max_lng / step_lng) + 1):
            yield round(i * step_lat, 4), round(j * step_lng, 4)


class _NearRoute:
    """Is a point within `radius_mi` of any route sample? Samples are bucketed
    in cells at least `radius_mi` wide, so only the 3x3 neighbouring cells are checked."""

    def __init__(self, samples: list[LatLng], radius_mi: float):
        self.radius = radius_mi
        max_lat = max(abs(lat) for lat, _ in samples)
        self.cell_lat = radius_mi / MILES_PER_DEGREE_LAT
        self.cell_lng = radius_mi / (MILES_PER_DEGREE_LAT * math.cos(math.radians(min(max_lat + 1, 89))))
        self.cells: dict[tuple[int, int], list[LatLng]] = {}
        for p in samples:
            self.cells.setdefault(self._cell(p), []).append(p)

    def _cell(self, p: LatLng) -> tuple[int, int]:
        return math.floor(p[0] / self.cell_lat), math.floor(p[1] / self.cell_lng)

    def __call__(self, p: LatLng) -> bool:
        ci, cj = self._cell(p)
        return any(
            haversine_mi(p, q) <= self.radius
            for di in (-1, 0, 1)
            for dj in (-1, 0, 1)
            for q in self.cells.get((ci + di, cj + dj), ())
        )
