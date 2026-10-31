import json
import time
from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from routing import views
from routing.services.errors import InvalidTrip, NoRouteFound, PlaceNotFound, ProviderError, ProviderTimeout


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

    def fake_plan(req, *, tomtom, weather, progress=None):
        calls.append(req)
        if progress:
            progress("places", "Looking up places")
            progress("routes", "Finding truck routes")
        if isinstance(planner.raises, Exception):
            raise planner.raises
        return {"ok": True}

    def fake_tomtom(key, deadline):
        planner.deadline = deadline
        return object()

    monkeypatch.setattr(views, "TomTomClient", fake_tomtom)
    monkeypatch.setattr(views, "OpenMeteoClient", lambda deadline: object())
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
        ({"departure": ""}, "departure"),
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
    assert "full 48-hour forecast" in response.json()["departure"][0]


class TestHeatmapEndpoint:
    @pytest.fixture
    def builder(self, monkeypatch):
        calls = []

        def fake_build(routes, *, load_lbs, start, weather):
            calls.append((routes, load_lbs, start))
            return {"hours": [], "spacing_mi": 8.0, "points": []}

        monkeypatch.setattr(views, "OpenMeteoClient", lambda deadline: object())
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
        (ProviderTimeout("slow"), 504),
    ],
)
def test_provider_errors(planner, error, code):
    planner.raises = error
    response = post(body())
    assert response.status_code == code
    assert response.json()["detail"]


class TestPlaces:
    @pytest.fixture
    def suggest(self, monkeypatch):
        from types import SimpleNamespace

        from routing.services.tomtom import Place

        state = SimpleNamespace(raises=None, queries=[])

        class FakeClient:
            def __init__(self, key, deadline):
                pass

            def suggest(self, query):
                if state.raises:
                    raise state.raises
                state.queries.append(query)
                return [Place("Dallas, TX", 32.78, -96.8)]

        monkeypatch.setattr(views, "TomTomClient", FakeClient)
        return state

    def test_returns_places(self, suggest):
        response = Client().get("/api/places", {"q": " Dall "})
        assert response.status_code == 200
        assert response.json() == {"places": [{"label": "Dallas, TX", "lat": 32.78, "lng": -96.8}]}
        assert suggest.queries == ["Dall"]

    def test_too_short(self, suggest):
        assert Client().get("/api/places", {"q": "D"}).status_code == 400
        assert suggest.queries == []

    def test_provider_failure(self, suggest):
        suggest.raises = ProviderError("down")
        response = Client().get("/api/places", {"q": "Dall"})
        assert response.status_code == 502
        assert response.json()["detail"]


class TestPlanStream:
    def stream(self, data):
        response = Client().post("/api/plan/stream", data, content_type="application/json")
        return response, [json.loads(line) for line in b"".join(response.streaming_content).splitlines()]

    def test_progress_then_result(self, planner):
        response, events = self.stream(body())
        assert response.status_code == 200
        assert response["Content-Type"] == "application/x-ndjson"
        # Not gzipped: GZipMiddleware would hold every line back until the end.
        assert response["Content-Encoding"] == "identity"
        assert [e["type"] for e in events] == ["progress", "progress", "result"]
        assert events[0] == {"type": "progress", "step": "places", "message": "Looking up places"}
        assert events[-1]["plan"] == {"ok": True}

    @pytest.mark.parametrize(
        "error, code",
        [(PlaceNotFound("Atlantis"), 422), (ProviderTimeout("slow"), 504), (ProviderError("boom"), 502)],
    )
    def test_errors_arrive_as_an_event(self, planner, error, code):
        planner.raises = error
        _, events = self.stream(body())
        assert events[-1]["type"] == "error"
        assert events[-1]["status"] == code
        assert events[-1]["detail"]

    def test_invalid_input_is_a_plain_400(self, planner):
        response = Client().post("/api/plan/stream", body(load_lbs=0), content_type="application/json")
        assert response.status_code == 400
        assert "load_lbs" in response.json()
        assert planner.calls == []


def test_requests_get_a_time_budget_under_herokus_limit(planner):
    started = time.monotonic()
    post(body())
    assert 0 < planner.deadline - started <= 30
