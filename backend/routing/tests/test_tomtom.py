import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from django.core.cache.backends.locmem import LocMemCache

from routing.services.errors import NoRouteFound, PlaceNotFound, ProviderError, ProviderTimeout
from routing.services.tomtom import TomTomClient


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class FakeSession:
    """Returns `response` for every call, or each of `responses` in turn."""

    def __init__(self, response=None, error=None, responses=None):
        self.responses = list(responses) if responses else None
        self.response = response
        self.error = error
        self.calls = []

    def get(self, url, params, timeout):
        self.calls.append((url, params))
        if self.error:
            raise self.error
        return self.responses.pop(0) if self.responses else self.response


def client_with(response=None, error=None, responses=None):
    session = FakeSession(response, error, responses)
    cache = LocMemCache(f"test-{uuid.uuid4()}", {})
    return TomTomClient("test-key", session=session, cache=cache), session


def geocode_payload(label="Dallas, TX", confidence=1.0):
    return {
        "results": [
            {
                "address": {"freeformAddress": label},
                "position": {"lat": 32.78, "lon": -96.8},
                "matchConfidence": {"score": confidence},
            }
        ]
    }


ROUTE_PAYLOAD = {
    "routes": [
        {
            "summary": {"lengthInMeters": 4000, "travelTimeInSeconds": 300},
            "legs": [
                {"points": [{"latitude": 32.0, "longitude": -97.0}, {"latitude": 32.01, "longitude": -97.0}]},
                {"points": [{"latitude": 32.01, "longitude": -97.0}, {"latitude": 32.02, "longitude": -97.0}]},
            ],
            "progress": [
                {"pointIndex": 0, "distanceInMeters": 0, "travelTimeInSeconds": 0},
                {"pointIndex": 3, "distanceInMeters": 4000, "travelTimeInSeconds": 300},
            ],
        }
    ]
}


class TestGeocode:
    def test_parses_top_result(self):
        client, session = client_with(FakeResponse(payload=geocode_payload()))
        place = client.geocode("Dallas, TX")
        assert (place.label, place.lat, place.lng) == ("Dallas, TX", 32.78, -96.8)
        url, params = session.calls[0]
        assert url.endswith("/search/2/geocode/Dallas%2C%20TX.json")
        assert ("key", "test-key") in params
        assert ("countrySet", "US") in params  # "US,CA" misreads "WY" as "Way"

    def test_no_results(self):
        client, _ = client_with(FakeResponse(payload={"results": []}))
        with pytest.raises(PlaceNotFound):
            client.geocode("Nowhere at all")

    def test_weak_match_is_rejected(self):
        # Live example: "Qwxzzy Nowhere" -> "Nowhere Road, VA" with confidence 0.601.
        client, _ = client_with(FakeResponse(payload=geocode_payload("Nowhere Road, VA", 0.601)))
        with pytest.raises(PlaceNotFound):
            client.geocode("Qwxzzy Nowhere")

    def test_results_are_cached_by_normalized_text(self):
        client, session = client_with(FakeResponse(payload=geocode_payload()))
        client.geocode("Dallas, TX")
        client.geocode("  dallas,   tx ")
        assert len(session.calls) == 1


class TestCalculateRoutes:
    def test_request_parameters(self):
        client, session = client_with(FakeResponse(payload=ROUTE_PAYLOAD))
        depart = datetime(2026, 11, 2, 6, 0, tzinfo=timezone(timedelta(hours=-6)))
        client.calculate_routes(
            [(32.0, -97.0), (32.02, -97.0)], load_lbs=36000, depart_at=depart, max_alternatives=2
        )
        url, params = session.calls[0]
        assert url.endswith("/calculateRoute/32.000000,-97.000000:32.020000,-97.000000/json")
        assert ("vehicleWeight", 16329) in params  # 36,000 lb in kg
        assert ("travelMode", "truck") in params
        assert ("maxAlternatives", 2) in params
        assert ("departAt", "2026-11-02T12:00:00Z") in params
        assert [v for k, v in params if k == "extendedRouteRepresentation"] == ["distance", "travelTime"]

    def test_parses_legs_and_progress(self):
        client, _ = client_with(FakeResponse(payload=ROUTE_PAYLOAD))
        [route] = client.calculate_routes(
            [(32.0, -97.0), (32.02, -97.0)], load_lbs=1000, depart_at=datetime.now(timezone.utc)
        )
        assert len(route.points) == 4  # shared leg end point kept, matching progress indexes
        assert route.travel_time_s == 300
        assert route.progress == [(0, 0.0), (3, 300.0)]

    def test_no_route_found(self):
        client, _ = client_with(FakeResponse(400, text='{"error":{"description":"NO_ROUTE_FOUND"}}'))
        with pytest.raises(NoRouteFound):
            client.calculate_routes([(0, 0), (1, 1)], load_lbs=1, depart_at=datetime.now(timezone.utc))


class TestFailures:
    def test_http_error_after_retry(self):
        client, session = client_with(FakeResponse(500, text="boom"))
        with pytest.raises(ProviderError):
            client.geocode("Dallas")
        assert len(session.calls) == 2

    def test_temporary_error_is_retried(self):
        client, session = client_with(
            responses=[FakeResponse(503, text="busy"), FakeResponse(payload=geocode_payload())]
        )
        assert client.geocode("Dallas, TX").label == "Dallas, TX"
        assert len(session.calls) == 2

    def test_client_error_is_not_retried(self):
        client, session = client_with(FakeResponse(403, text="forbidden"))
        with pytest.raises(ProviderError):
            client.geocode("Dallas")
        assert len(session.calls) == 1

    def test_network_error(self):
        client, _ = client_with(error=requests.ConnectionError())
        with pytest.raises(ProviderError):
            client.geocode("Dallas")

    def test_timeout_is_reported_as_timeout(self):
        client, _ = client_with(error=requests.Timeout())
        with pytest.raises(ProviderTimeout):
            client.geocode("Dallas")

    def test_bad_json(self):
        client, _ = client_with(FakeResponse(200, payload=None))
        with pytest.raises(ProviderError):
            client.geocode("Dallas")

    def test_missing_key(self):
        with pytest.raises(ProviderError):
            TomTomClient("")
