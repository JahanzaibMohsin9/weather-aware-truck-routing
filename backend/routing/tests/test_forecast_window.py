from datetime import datetime, timedelta, timezone

import pytest

from routing.domain.forecast import FORECAST_DAYS, start_limit
from routing.serializers import HeatmapRequestSerializer, PlanRequestSerializer
from routing.services.heatmap import build_heatmap
from routing.services.weather import HourlySeries


@pytest.mark.parametrize("hour", [0, 12, 23])
def test_latest_accepted_departure_has_all_49_forecast_frames(monkeypatch, hour):
    now = datetime(2026, 10, 31, hour, 59, tzinfo=timezone.utc)
    monkeypatch.setattr("routing.serializers.timezone.now", lambda: now)
    limit = start_limit(now)
    departure = limit - timedelta(microseconds=1)
    routes = [[[-100, 38], [-99.5, 38]]]
    plan = PlanRequestSerializer(data={
        "origin": "Dallas", "destination": "Denver", "load_lbs": 36000,
        "departure": departure.isoformat(),
    })
    heat = HeatmapRequestSerializer(data={"routes": routes, "load_lbs": 36000, "start": departure.isoformat()})
    assert plan.is_valid(), plan.errors
    assert heat.is_valid(), heat.errors

    class Weather:
        def series_for(self, points):
            midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
            n = FORECAST_DAYS * 24
            return [HourlySeries(int(midnight.timestamp()), [10.] * n, [12.] * n,
                                 [0.] * n, [0.] * n, [0.] * n) for _ in points]

    result = build_heatmap([[(38, -100), (38, -99.5)]], load_lbs=36000, start=departure, weather=Weather())
    assert len(result["hours"]) == 49
    assert result["points"]
    assert all(all(v is not None for v in p["score"]) for p in result["points"])

    # Reject the first hour whose +48 frame needs precipitation beyond the end.
    for serializer, field in [(plan, "departure"), (heat, "start")]:
        invalid = serializer.__class__(data={**serializer.initial_data, field: limit.isoformat()})
        assert not invalid.is_valid()
        assert "full 48-hour forecast" in invalid.errors[field][0]


def test_cutoff_uses_utc_calendar_day():
    now = datetime(2026, 11, 1, 1, tzinfo=timezone(timedelta(hours=5)))
    assert start_limit(now) == datetime(2026, 11, 13, 23, tzinfo=timezone.utc)
