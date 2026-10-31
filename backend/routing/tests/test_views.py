from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from routing import views
from routing.services.errors import InvalidTrip, NoRouteFound, PlaceNotFound, ProviderError


def test_health():
    response = Client().get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def body(**overrides):
    data = {
        "origin": "Dallas, TX",
        "destination": "Denver, CO",
        "departure": (timezone.now() + timedelta(hours=2)).isoformat(),
        "load_lbs": 36000,
        "interval_miles": 25,
    }
    data.update(overrides)
    return data


def post(data):
    return Client().post("/api/plan", data, content_type="application/json")


@pytest.fixture
def planner(monkeypatch):
    """Replace the providers and planner so no request leaves the test."""
    calls = []

    def fake_plan(req, *, tomtom, weather):
        calls.append(req)
        if isinstance(planner.raises, Exception):
            raise planner.raises
        return {"ok": True}

    monkeypatch.setattr(views, "TomTomClient", lambda key: object())
    monkeypatch.setattr(views, "OpenMeteoClient", lambda: object())
    monkeypatch.setattr(views, "plan_trip", fake_plan)
    planner.raises = None
    planner.calls = calls
    return planner


def test_valid_request_reaches_planner(planner):
    response = post(body(interval_miles=10))
    assert response.status_code == 200
    assert planner.calls[0].interval_miles == 10
    assert planner.calls[0].load_lbs == 36000


def test_interval_defaults_to_25(planner):
    data = body()
    del data["interval_miles"]
    post(data)
    assert planner.calls[0].interval_miles == 25


@pytest.mark.parametrize(
    "overrides, field",
    [
        ({"load_lbs": 0}, "load_lbs"),
        ({"load_lbs": -5}, "load_lbs"),
        ({"interval_miles": 30}, "interval_miles"),
        ({"departure": "2020-01-01T00:00:00Z"}, "departure"),
        ({"destination": "  dallas,   tx "}, "destination"),
        ({"origin": ""}, "origin"),
    ],
)
def test_validation_errors(planner, overrides, field):
    response = post(body(**overrides))
    assert response.status_code == 400
    assert field in response.json()
    assert planner.calls == []


def test_departure_more_than_14_days_ahead(planner):
    response = post(body(departure=(timezone.now() + timedelta(days=15)).isoformat()))
    assert response.status_code == 400
    assert "14 days" in response.json()["departure"][0]


class TestHeatmapEndpoint:
    @pytest.fixture
    def builder(self, monkeypatch):
        calls = []

        def fake_build(routes, *, load_lbs, start, weather):
            calls.append((routes, load_lbs, start))
            return {"hours": [], "spacing_mi": 8.0, "points": []}

        monkeypatch.setattr(views, "OpenMeteoClient", lambda: object())
        monkeypatch.setattr(views, "build_heatmap", fake_build)
        return calls

    def body(self, **overrides):
        data = {
            "routes": [[[-96.8, 32.78], [-97.0, 33.0]]],
            "load_lbs": 36000,
            "start": (timezone.now() + timedelta(hours=1)).isoformat(),
        }
        data.update(overrides)
        return data

    def post(self, data):
        return Client().post("/api/heatmap", data, content_type="application/json")

    def test_converts_lng_lat_to_lat_lng(self, builder):
        assert self.post(self.body()).status_code == 200
        routes, load, _ = builder[0]
        assert routes == [[(32.78, -96.8), (33.0, -97.0)]]
        assert load == 36000

    @pytest.mark.parametrize(
        "overrides",
        [
            {"routes": []},
            {"routes": [[[-96.8]]]},
            {"routes": [[[200, 32]]]},
            {"routes": [[[-96.8, 32.78]]] * 4},
            {"load_lbs": 0},
            {"start": "2020-01-01T00:00:00Z"},
        ],
    )
    def test_validation(self, builder, overrides):
        assert self.post(self.body(**overrides)).status_code == 400
        assert builder == []


@pytest.mark.parametrize(
    "error, code",
    [
        (PlaceNotFound("Atlantis"), 422),
        (NoRouteFound("x"), 422),
        (InvalidTrip("Origin and destination are the same place."), 422),
        (ProviderError("boom"), 502),
    ],
)
def test_provider_errors(planner, error, code):
    planner.raises = error
    response = post(body())
    assert response.status_code == code
    assert response.json()["detail"]
