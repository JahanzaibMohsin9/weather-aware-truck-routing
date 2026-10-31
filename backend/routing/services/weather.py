"""Open-Meteo hourly forecasts for many points, with caching.

Coordinates are rounded to 0.01° (about 0.7 mi) before fetching. That is finer
than the weather models' grid, and it lets nearby checkpoints and repeat trips
share cached forecasts.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

import requests
from django.core.cache import cache as default_cache

from ..domain.geo import LatLng
from ..domain.forecast import FORECAST_DAYS
from .errors import ProviderError, ProviderTimeout
from .http import get_with_retry

URL = "https://api.open-meteo.com/v1/forecast"
HOURLY = ("wind_speed_10m", "wind_gusts_10m", "rain", "showers", "snowfall")
CHUNK_SIZE = 100  # locations per request, keeps URLs short
CACHE_SECONDS = 30 * 60
COORD_DECIMALS = 2


@dataclass(frozen=True)
class HourlySeries:
    """One location's forecast. Index i is the hour starting at start + i*3600.

    Open-Meteo stamps rain, showers and snowfall at the *end* of the hour they
    fell in; wind and gusts are instantaneous at the timestamp.
    """

    start: int  # unix seconds
    wind: list[float | None]
    gust: list[float | None]
    rain: list[float | None]
    showers: list[float | None]
    snow: list[float | None]


@dataclass(frozen=True)
class Weather:
    wind_mph: float
    gust_mph: float | None
    rain_in_hr: float  # rain + showers
    snow_in_hr: float


def weather_at(series: HourlySeries, when: datetime) -> Weather | None:
    """Conditions at `when`, or None if it is outside the forecast."""
    hours = (when.timestamp() - series.start) / 3600
    wind_i = round(hours)  # nearest hour
    precip_i = math.floor(hours) + 1  # the value stamped at the end of the hour we're in
    if wind_i < 0 or precip_i >= len(series.rain):
        return None
    wind, rain, showers, snow = (
        series.wind[wind_i],
        series.rain[precip_i],
        series.showers[precip_i],
        series.snow[precip_i],
    )
    if wind is None or rain is None or showers is None or snow is None:
        return None
    return Weather(
        wind_mph=wind,
        gust_mph=series.gust[wind_i],
        # Rounded so 0.07 + 0.03 is 0.10 (Moderate), not 0.0999... (Low).
        rain_in_hr=round(rain + showers, 4),
        snow_in_hr=snow,
    )


def _key(point: LatLng) -> str:
    return f"om:{point[0]:.{COORD_DECIMALS}f},{point[1]:.{COORD_DECIMALS}f}"


class OpenMeteoClient:
    def __init__(
        self,
        session: requests.Session | None = None,
        cache=None,
        timeout: float = 20,
        deadline: float | None = None,
    ):
        """`deadline` (a `time.monotonic()` value) bounds every call this client makes."""
        self.session = session or requests.Session()
        self.cache = cache if cache is not None else default_cache
        self.timeout = timeout
        self.deadline = deadline

    def series_for(self, points: Sequence[LatLng]) -> list[HourlySeries]:
        """A forecast for each point, in the same order. Fetches only uncached ones."""
        keys = [_key(p) for p in points]
        found: dict[str, HourlySeries] = self.cache.get_many(list(dict.fromkeys(keys)))
        missing = list(dict.fromkeys(k for k in keys if k not in found))
        for i in range(0, len(missing), CHUNK_SIZE):
            fetched = self._fetch(missing[i : i + CHUNK_SIZE])
            self.cache.set_many(fetched, CACHE_SECONDS)
            found.update(fetched)
        return [found[k] for k in keys]

    def _fetch(self, keys: list[str]) -> dict[str, HourlySeries]:
        coords = [k.removeprefix("om:").split(",") for k in keys]
        params = {
            "latitude": ",".join(lat for lat, _ in coords),
            "longitude": ",".join(lng for _, lng in coords),
            "hourly": ",".join(HOURLY),
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "timezone": "GMT",
            "timeformat": "unixtime",
            "forecast_days": FORECAST_DAYS,
        }
        try:
            response = get_with_retry(
                self.session, URL, params=params, timeout=self.timeout, deadline=self.deadline
            )
        except requests.Timeout as exc:
            raise ProviderTimeout("Open-Meteo was too slow") from exc
        except requests.RequestException as exc:
            raise ProviderError(f"Open-Meteo request failed: {exc.__class__.__name__}") from exc
        if response.status_code != 200:
            raise ProviderError(f"Open-Meteo returned HTTP {response.status_code}")
        try:
            data = response.json()
            locations = data if isinstance(data, list) else [data]  # one location -> one object
            if len(locations) != len(keys):
                raise ProviderError("Open-Meteo returned the wrong number of locations")
            return {key: self._parse(location["hourly"]) for key, location in zip(keys, locations)}
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            raise ProviderError("Open-Meteo returned an unexpected response") from exc

    @staticmethod
    def _parse(hourly: dict) -> HourlySeries:
        return HourlySeries(
            start=int(hourly["time"][0]),
            wind=hourly["wind_speed_10m"],
            gust=hourly["wind_gusts_10m"],
            rain=hourly["rain"],
            showers=hourly["showers"],
            snow=hourly["snowfall"],
        )
