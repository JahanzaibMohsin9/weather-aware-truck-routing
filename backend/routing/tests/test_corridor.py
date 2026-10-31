from datetime import datetime, timedelta, timezone

import pytest

from routing.domain.corridor import corridor_grid
from routing.domain.geo import haversine_mi, resample
from routing.services.heatmap import HOURS, build_heatmap
from routing.services.weather import HourlySeries

# ~620 miles east-west across Kansas/Missouri
ROUTE = [(38.5, -101.0), (38.5, -95.0), (38.6, -90.2)]


def nearest_route_mi(p):
    return min(haversine_mi(p, q) for q in resample(ROUTE, 1))


class TestCorridorGrid:
    def test_points_stay_in_the_corridor(self):
        points, _ = corridor_grid([ROUTE])
        assert points
        assert all(nearest_route_mi(p) <= 30.01 for p in points)

    def test_respects_point_cap(self):
        points, spacing = corridor_grid([ROUTE], max_points=60)
        assert len(points) <= 60
        assert spacing > 8

    def test_covers_the_whole_route(self):
        points, spacing = corridor_grid([ROUTE])
        # Every mile of the route has a grid point within one grid diagonal.
        for p in resample(ROUTE, 10):
            assert min(haversine_mi(p, g) for g in points) <= spacing * 0.75

    def test_grid_is_stable_for_overlapping_requests(self):
        # Same area, slightly different route -> the shared points are identical
        # (so their cached forecasts are reused).
        a, sa = corridor_grid([ROUTE])
        b, sb = corridor_grid([[(38.5, -101.0), (38.5, -95.0), (38.6, -90.2), (38.6, -90.1)]])
        assert sa == sb
        assert len(set(a) & set(b)) >= 0.9 * len(a)

    def test_empty(self):
        assert corridor_grid([]) == ([], 8.0)


class FakeWeather:
    """Wind = hour index everywhere, so the heat score climbs over time."""

    def __init__(self, hours=72):
        self.hours = hours
        self.requested = 0

    def series_for(self, points):
        self.requested += len(points)
        start = int(datetime(2026, 11, 2, tzinfo=timezone.utc).timestamp())
        n = self.hours
        return [HourlySeries(start, [float(i) for i in range(n)], [None] * n, [0.0] * n, [0.0] * n, [0.0] * n)
                for _ in points]


class TestBuildHeatmap:
    def test_shape_and_hours(self):
        result = build_heatmap([ROUTE], load_lbs=10000, start=datetime(2026, 11, 2, 6, 40, tzinfo=timezone.utc),
                               weather=FakeWeather())
        assert len(result["hours"]) == HOURS
        assert result["hours"][0] == "2026-11-02T06:00:00Z"  # rounded down to the hour
        assert result["hours"][-1] == "2026-11-04T06:00:00Z"
        point = result["points"][0]
        assert all(len(point[k]) == HOURS for k in ("level", "score", "wind", "rain", "snow"))

    def test_values_follow_the_risk_rules(self):
        result = build_heatmap([ROUTE], load_lbs=45000, start=datetime(2026, 11, 2, 0, tzinfo=timezone.utc),
                               weather=FakeWeather())
        point = result["points"][0]
        assert point["wind"][12] == 12 and point["level"][12] == 0 and point["score"][12] == pytest.approx(0.48)
        assert point["level"][30] == 1  # 30 mph: Moderate
        assert point["level"][40] == 3  # 40 mph with 45,000 lb: Severe via the load rule
        assert point["level"][48] == 4  # 48 mph with 45,000 lb: No Travel via the load rule
        assert point["score"][48] == 4

    def test_includes_the_threshold_scales(self):
        result = build_heatmap([ROUTE], load_lbs=1, start=datetime(2026, 11, 2, tzinfo=timezone.utc),
                               weather=FakeWeather())
        assert result["scales"] == {"wind": [25, 35, 45, 55], "rain": [0.10, 0.25, 0.50, 1.00], "snow": [0.5, 1.0, 2.0, 3.0]}

    def test_hours_past_the_forecast_are_null(self):
        result = build_heatmap([ROUTE], load_lbs=1, start=datetime(2026, 11, 2, 0, tzinfo=timezone.utc),
                               weather=FakeWeather(hours=30))
        point = result["points"][0]
        assert point["level"][28] is not None
        assert point["level"][29] is None and point["score"][29] is None

    def test_one_weather_request_per_grid_point(self):
        weather = FakeWeather()
        result = build_heatmap([ROUTE, ROUTE], load_lbs=1, start=datetime(2026, 11, 2, tzinfo=timezone.utc),
                               weather=weather)
        assert weather.requested == len(result["points"])
