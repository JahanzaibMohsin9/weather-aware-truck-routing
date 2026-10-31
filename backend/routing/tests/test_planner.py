"""The planner end to end, with fake routing and weather providers."""

from datetime import datetime, timedelta, timezone

import pytest

from routing.services.errors import InvalidTrip
from routing.services.planner import PlanRequest, plan_trip
from routing.services.tomtom import Place, RawRoute
from routing.services.weather import HourlySeries

NOW = datetime(2026, 11, 2, 10, 0, tzinfo=timezone.utc)
DEPART = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
ORIGIN = Place("Origin, TX", 32.0, -100.0)
DESTINATION = Place("Destination, TX", 32.0, -99.0)  # ~59 mi east

STRAIGHT = RawRoute([(32.0, -100.0), (32.0, -99.0)], travel_time_s=3600, progress=[])
NORTH = RawRoute([(32.0, -100.0), (32.5, -99.5), (32.0, -99.0)], travel_time_s=4800, progress=[])
SOUTH = RawRoute([(32.0, -100.0), (31.5, -99.5), (32.0, -99.0)], travel_time_s=5400, progress=[])


class FakeTomTom:
    def __init__(self, routes=(STRAIGHT, NORTH, SOUTH)):
        self.routes = list(routes)
        self.depart_at = None

    def geocode(self, query):
        return {"origin": ORIGIN, "destination": DESTINATION, "same": ORIGIN}[query]

    def calculate_routes(self, locations, *, load_lbs, depart_at, route_type="fastest", max_alternatives=0):
        self.depart_at = depart_at
        return self.routes


class FakeWeather:
    """Calm everywhere, except gale-force wind north of 32.2° (only the NORTH route goes there)."""

    def __init__(self, hours=48):
        self.hours = hours

    def series_for(self, points):
        start = int(datetime(2026, 11, 2, tzinfo=timezone.utc).timestamp())
        out = []
        for lat, _ in points:
            wind = 50.0 if lat > 32.2 else 5.0
            out.append(HourlySeries(start, [wind] * self.hours, [wind + 5] * self.hours,
                                    [0.0] * self.hours, [0.0] * self.hours, [0.0] * self.hours))
        return out


def plan(tomtom=None, weather=None, destination="destination", load=36000, interval=10, departure=DEPART):
    req = PlanRequest("origin", destination, departure, load, interval)
    return plan_trip(req, tomtom=tomtom or FakeTomTom(), weather=weather or FakeWeather(), now=NOW)


def test_recommends_the_safe_fast_route():
    result = plan()
    assert [r["id"] for r in result["routes"]] == ["A", "B", "C"]
    assert result["recommended_route_id"] == "A"
    a, b, c = result["routes"]
    assert (a["rank"], c["rank"], b["rank"]) == (1, 2, 3)
    assert a["recommended"] and not b["recommended"]
    # 50 mph wind with 36,000 lb (> 30,000) is No Travel on the northern route.
    assert b["summary"]["has_no_travel"]
    assert any(cp["level"] == "No Travel" for cp in b["checkpoints"])
    assert result["explanation"].startswith("Route A: same weather risk as Route C")


def test_checkpoint_payload():
    cp = plan()["routes"][0]["checkpoints"][1]
    assert cp["mile"] == pytest.approx(10)
    assert cp["eta"] == "2026-11-02T12:10:" + cp["eta"][-3:]  # 10 of ~59 mi in 1 h
    assert cp["level"] == "Low"
    assert (cp["wind_mph"], cp["gust_mph"], cp["rain_in_hr"]) == (5.0, 10.0, 0.0)


def test_geometry_is_lng_lat():
    first = plan()["routes"][0]["geometry"][0]
    assert first == [-100.0, 32.0]


def test_missing_forecast_is_reported():
    result = plan(weather=FakeWeather(hours=13))  # forecast ends 13:00, trip ends after it
    route = result["routes"][0]
    assert not route["summary"]["forecast_complete"]
    assert route["checkpoints"][-1]["level"] == "No Forecast"
    assert any("forecast ends" in note for note in result["notes"])


def test_past_departure_is_sent_to_tomtom_as_now():
    tomtom = FakeTomTom()
    plan(tomtom=tomtom, departure=NOW - timedelta(minutes=2))
    assert tomtom.depart_at == NOW + timedelta(minutes=1)


def test_reports_progress_in_order():
    steps = []
    plan_trip(PlanRequest("origin", "destination", DEPART, 36000, 10), tomtom=FakeTomTom(),
              weather=FakeWeather(), now=NOW, progress=lambda step, message: steps.append((step, message)))
    assert [step for step, _ in steps] == ["places", "routes", "forecast", "scoring"]
    assert steps[1][1] == "Finding truck routes from Origin, TX to Destination, TX"


def test_same_place_is_rejected():
    with pytest.raises(InvalidTrip):
        plan(destination="same")  # different text, same geocoded place
