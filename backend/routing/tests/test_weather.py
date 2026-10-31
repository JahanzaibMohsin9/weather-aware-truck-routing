import uuid
from datetime import datetime, timezone

import pytest
import requests
from django.core.cache.backends.locmem import LocMemCache

from routing.services.errors import ProviderError, ProviderTimeout
from routing.services.weather import HourlySeries, OpenMeteoClient, weather_at

START = datetime(2026, 11, 2, 0, 0, tzinfo=timezone.utc)
T0 = int(START.timestamp())


def at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 11, 2, hour, minute, tzinfo=timezone.utc)


def series(hours=24, **overrides):
    values = {
        "wind": [float(i) for i in range(hours)],  # wind == hour index, easy to read back
        "gust": [float(i) + 10 for i in range(hours)],
        "rain": [i / 100 for i in range(hours)],  # rain == hour index / 100
        "showers": [0.0] * hours,
        "snow": [0.0] * hours,
    }
    values.update(overrides)
    return HourlySeries(start=T0, **values)


class TestWeatherAt:
    def test_wind_uses_nearest_hour(self):
        assert weather_at(series(), at(14, 20)).wind_mph == 14
        assert weather_at(series(), at(14, 40)).wind_mph == 15

    def test_precipitation_uses_the_hour_being_driven(self):
        # 14:20 falls in 14:00-15:00, which Open-Meteo stamps at 15:00.
        assert weather_at(series(), at(14, 20)).rain_in_hr == pytest.approx(0.15)
        assert weather_at(series(), at(14, 0)).rain_in_hr == pytest.approx(0.15)

    def test_rain_includes_showers_without_float_noise(self):
        s = series(rain=[0.07] * 24, showers=[0.03] * 24)
        assert weather_at(s, at(3)).rain_in_hr == 0.10

    def test_beyond_forecast_is_none(self):
        assert weather_at(series(hours=24), at(23, 10)) is None  # needs the 24:00 value

    def test_before_forecast_is_none(self):
        assert weather_at(series(), datetime(2026, 11, 1, 22, tzinfo=timezone.utc)) is None

    def test_null_values_are_none(self):
        s = series(rain=[None] * 24)
        assert weather_at(s, at(3)) is None


def hourly(n=3):
    return {
        "time": [T0 + 3600 * i for i in range(n)],
        "wind_speed_10m": [5.0] * n,
        "wind_gusts_10m": [9.0] * n,
        "rain": [0.0] * n,
        "showers": [0.0] * n,
        "snowfall": [0.0] * n,
    }


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self.payload = payload

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, error=None, status=200):
        self.calls = []
        self.error = error
        self.status = status

    def get(self, url, params, timeout):
        self.calls.append(params)
        if self.error:
            raise self.error
        count = len(params["latitude"].split(","))
        payload = [{"hourly": hourly()} for _ in range(count)]
        return FakeResponse(self.status, payload[0] if count == 1 else payload)


def client(session):
    # LocMemCache instances with the same name share storage, so each test needs a unique name.
    return OpenMeteoClient(session=session, cache=LocMemCache(f"test-{uuid.uuid4()}", {}))


class TestClient:
    def test_request_parameters(self):
        session = FakeSession()
        client(session).series_for([(32.7767, -96.797), (39.7392, -104.9903)])
        params = session.calls[0]
        assert params["latitude"] == "32.78,39.74"
        assert params["longitude"] == "-96.80,-104.99"
        assert params["hourly"] == "wind_speed_10m,wind_gusts_10m,rain,showers,snowfall"
        assert (params["wind_speed_unit"], params["precipitation_unit"]) == ("mph", "inch")

    def test_single_location_response(self):
        [result] = client(FakeSession()).series_for([(32.78, -96.8)])
        assert result.start == T0
        assert result.gust == [9.0, 9.0, 9.0]

    def test_nearby_points_share_one_location_and_order_is_kept(self):
        session = FakeSession()
        results = client(session).series_for([(32.781, -96.801), (40.0, -100.0), (32.779, -96.799)])
        assert len(results) == 3
        assert session.calls[0]["latitude"] == "32.78,40.00"

    def test_cache_avoids_refetch(self):
        session = FakeSession()
        c = client(session)
        c.series_for([(32.78, -96.8)])
        c.series_for([(32.78, -96.8), (40.0, -100.0)])
        assert [p["latitude"] for p in session.calls] == ["32.78", "40.00"]

    def test_chunks_large_batches(self):
        session = FakeSession()
        points = [(30 + i / 10, -100.0) for i in range(250)]
        assert len(client(session).series_for(points)) == 250
        assert [len(p["latitude"].split(",")) for p in session.calls] == [100, 100, 50]

    def test_http_error(self):
        with pytest.raises(ProviderError):
            client(FakeSession(status=429)).series_for([(32.78, -96.8)])

    def test_network_error(self):
        with pytest.raises(ProviderError):
            client(FakeSession(error=requests.ConnectionError())).series_for([(32.78, -96.8)])

    def test_timeout_is_reported_as_timeout(self):
        with pytest.raises(ProviderTimeout):
            client(FakeSession(error=requests.Timeout())).series_for([(32.78, -96.8)])
