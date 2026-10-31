"""Weather risk on the corridor grid for every hour from departure to +48 h.

Everything for all 49 hours goes to the browser in one response, so moving
the forecast slider never waits on the network.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Sequence

from ..domain.corridor import corridor_grid
from ..domain.geo import LatLng
from ..domain.risk import assess, heat_score
from .weather import OpenMeteoClient, weather_at

HOURS = 49  # 0..48


def build_heatmap(
    routes: Sequence[Sequence[LatLng]],
    *,
    load_lbs: float,
    start: datetime,
    weather: OpenMeteoClient,
) -> dict:
    hour0 = start.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    times = [hour0 + timedelta(hours=h) for h in range(HOURS)]
    grid, spacing = corridor_grid(routes)

    points = []
    for (lat, lng), series in zip(grid, weather.series_for(grid)):
        level, score, wind, rain, snow = [], [], [], [], []
        for t in times:
            w = weather_at(series, t)
            if w is None:  # past the end of the forecast: no heat, never "Low"
                for values in (level, score, wind, rain, snow):
                    values.append(None)
                continue
            a = assess(wind_mph=w.wind_mph, rain_in_hr=w.rain_in_hr, snow_in_hr=w.snow_in_hr, load_lbs=load_lbs)
            level.append(int(a.level))
            score.append(round(heat_score(
                wind_mph=w.wind_mph, rain_in_hr=w.rain_in_hr, snow_in_hr=w.snow_in_hr, level=a.level
            ), 2))
            wind.append(round(w.wind_mph, 1))
            rain.append(round(w.rain_in_hr, 3))
            snow.append(round(w.snow_in_hr, 2))
        points.append(
            {"lat": lat, "lng": lng, "level": level, "score": score, "wind": wind, "rain": rain, "snow": snow}
        )

    return {
        "hours": [t.strftime("%Y-%m-%dT%H:%M:%SZ") for t in times],
        "spacing_mi": spacing,
        "points": points,
    }
