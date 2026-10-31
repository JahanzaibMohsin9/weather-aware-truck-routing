"""TomTom Search (geocoding) and Routing API client.

Only this module knows TomTom's request and response shapes; it returns
plain dataclasses so the rest of the backend doesn't depend on them.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import quote

import requests
from django.core.cache import cache as default_cache

from ..domain.geo import LatLng
from .errors import NoRouteFound, PlaceNotFound, ProviderError, ProviderTimeout
from .http import get_with_retry

BASE_URL = "https://api.tomtom.com"
KG_PER_LB = 0.45359237
# US only: with "US,CA" TomTom reads state codes as street suffixes
# ("Cheyenne, WY" -> "Cheyenne Way, Nepean ON").
COUNTRY_SET = "US"
# Real places score 1.0; fuzzy guesses ("asdf" -> "Asaf Drive") score ~0.6-0.8.
MIN_MATCH_CONFIDENCE = 0.85
GEOCODE_CACHE_SECONDS = 24 * 3600


@dataclass(frozen=True)
class Place:
    label: str
    lat: float
    lng: float

    @property
    def point(self) -> LatLng:
        return self.lat, self.lng


@dataclass(frozen=True)
class RawRoute:
    points: list[LatLng]
    travel_time_s: float
    # (point index, cumulative seconds) pairs from TomTom's `progress` list.
    # It may skip points; times in between are interpolated.
    progress: list[tuple[int, float]]


class TomTomClient:
    def __init__(
        self,
        api_key: str,
        session: requests.Session | None = None,
        cache=None,
        timeout: float = 20,
        deadline: float | None = None,
    ):
        """`deadline` (a `time.monotonic()` value) bounds every call this client makes."""
        if not api_key:
            raise ProviderError("TOMTOM_API_KEY is not set")
        self.api_key = api_key
        self.session = session or requests.Session()
        self.cache = cache if cache is not None else default_cache
        self.timeout = timeout
        self.deadline = deadline

    def geocode(self, query: str) -> Place:
        normalized = " ".join(query.lower().split())
        key = "geo:" + hashlib.sha1(normalized.encode()).hexdigest()
        place = self.cache.get(key)
        if place is None:
            place = self._geocode(query)
            self.cache.set(key, place, GEOCODE_CACHE_SECONDS)
        return place

    def _geocode(self, query: str) -> Place:
        data = self._get(
            f"/search/2/geocode/{quote(query, safe='')}.json",
            [("limit", 1), ("countrySet", COUNTRY_SET)],
        )
        results = data.get("results") or []
        if not results:
            raise PlaceNotFound(query)
        top = results[0]
        if top.get("matchConfidence", {}).get("score", 1) < MIN_MATCH_CONFIDENCE:
            raise PlaceNotFound(query)
        return Place(
            label=top.get("address", {}).get("freeformAddress", query),
            lat=top["position"]["lat"],
            lng=top["position"]["lon"],
        )

    def calculate_routes(
        self,
        locations: list[LatLng],
        *,
        load_lbs: float,
        depart_at: datetime,
        route_type: str = "fastest",
        max_alternatives: int = 0,
    ) -> list[RawRoute]:
        """Truck routes through `locations` (origin, optional via points, destination)."""
        path = ":".join(f"{lat:.6f},{lng:.6f}" for lat, lng in locations)
        params = [
            ("travelMode", "truck"),
            ("vehicleCommercial", "true"),
            ("vehicleWeight", round(load_lbs * KG_PER_LB)),
            ("routeType", route_type),
            ("maxAlternatives", max_alternatives),
            ("departAt", depart_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")),
            ("extendedRouteRepresentation", "distance"),
            ("extendedRouteRepresentation", "travelTime"),
        ]
        data = self._get(f"/routing/1/calculateRoute/{path}/json", params, no_route_ok=True)
        routes = data.get("routes") or []
        if not routes:
            raise NoRouteFound(path)
        return [self._parse_route(route) for route in routes]

    def _parse_route(self, route: dict) -> RawRoute:
        # Legs share their end points, so a via route repeats one point. Keep
        # it: `progress` indexes refer to the concatenated list as returned.
        points = [
            (p["latitude"], p["longitude"]) for leg in route.get("legs", []) for p in leg["points"]
        ]
        if len(points) < 2:
            raise ProviderError("route has no geometry")
        progress = [
            (int(item["pointIndex"]), float(item["travelTimeInSeconds"]))
            for item in route.get("progress", [])
            if "travelTimeInSeconds" in item
        ]
        return RawRoute(
            points=points,
            travel_time_s=float(route["summary"]["travelTimeInSeconds"]),
            progress=progress,
        )

    def _get(self, path: str, params: list, no_route_ok: bool = False) -> dict:
        try:
            response = get_with_retry(
                self.session,
                BASE_URL + path,
                params=[("key", self.api_key), *params],
                timeout=self.timeout,
                deadline=self.deadline,
            )
        except requests.Timeout as exc:
            raise ProviderTimeout("TomTom was too slow") from exc
        except requests.RequestException as exc:
            raise ProviderError(f"TomTom request failed: {exc.__class__.__name__}") from exc
        if no_route_ok and response.status_code in (400, 404) and "NO_ROUTE_FOUND" in response.text:
            raise NoRouteFound(path)
        if response.status_code != 200:
            raise ProviderError(f"TomTom returned HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError as exc:
            raise ProviderError("TomTom returned invalid JSON") from exc
