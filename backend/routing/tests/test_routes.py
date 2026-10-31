from datetime import datetime, timezone

import pytest

from routing.services.errors import NoRouteFound
from routing.services.routes import find_routes, to_planned
from routing.services.tomtom import RawRoute

ORIGIN = (32.0, -100.0)
DESTINATION = (32.0, -98.0)
DEPART = datetime(2026, 11, 2, 12, tzinfo=timezone.utc)


def raw(*points, seconds=3600.0, progress=()):
    return RawRoute(points=list(points), travel_time_s=seconds, progress=list(progress))


STRAIGHT = raw(ORIGIN, DESTINATION)
STRAIGHT_COPY = raw((32.001, -100.0), (32.001, -98.0))  # same road, ~0.07 mi off
NORTH = raw(ORIGIN, (33.0, -99.0), DESTINATION)
SOUTH = raw(ORIGIN, (31.0, -99.0), DESTINATION)
NORTH_COPY = raw(ORIGIN, (33.0005, -99.0), DESTINATION)
# STRAIGHT plus an out-and-back spur at the midpoint: less than half of it lies
# on STRAIGHT, but all of STRAIGHT lies on it.
STRAIGHT_WITH_DETOUR = raw(ORIGIN, (32.0, -99.0), (33.0, -99.0), (32.0, -99.0), DESTINATION)


class FakeClient:
    """Answers by request kind: main call, extra route types, via-point calls."""

    def __init__(self, main, by_type=None, via=None):
        self.main = main
        self.by_type = by_type or {}
        self.via = list(via or [])
        self.calls = []

    def calculate_routes(self, locations, *, load_lbs, depart_at, route_type="fastest", max_alternatives=0):
        if len(locations) == 3:
            self.calls.append("via")
            result = self.via.pop(0)
        else:
            self.calls.append(route_type)
            result = self.main if route_type == "fastest" else self.by_type.get(route_type, [])
        if isinstance(result, Exception):
            raise result
        return result


def run(client):
    return find_routes(client, ORIGIN, DESTINATION, load_lbs=36000, depart_at=DEPART)


def test_three_from_first_call_makes_one_request():
    client = FakeClient([STRAIGHT, NORTH, SOUTH])
    routes, notes = run(client)
    assert [r.source for r in routes] == ["fastest", "alternative", "alternative"]
    assert client.calls == ["fastest"]
    assert notes == []


def test_tops_up_with_route_types_then_via_and_drops_duplicates():
    client = FakeClient(
        main=[STRAIGHT, STRAIGHT_COPY],
        by_type={"shortest": [NORTH], "eco": [NORTH_COPY]},
        via=[[SOUTH]],
    )
    routes, notes = run(client)
    assert [r.source for r in routes] == ["fastest", "shortest", "via"]
    assert client.calls == ["fastest", "shortest", "eco", "via"]
    assert notes == []


def test_existing_route_plus_detour_is_a_duplicate():
    # Seen live on Dallas -> Denver: a via route that was the fastest route plus a detour.
    client = FakeClient(main=[STRAIGHT, NORTH], via=[[STRAIGHT_WITH_DETOUR], [SOUTH]])
    routes, _ = run(client)
    assert [r.source for r in routes] == ["fastest", "alternative", "via"]
    assert routes[2].points == SOUTH.points


def test_via_without_route_tries_other_side():
    client = FakeClient(main=[STRAIGHT], by_type={"shortest": [NORTH]}, via=[NoRouteFound("lake"), [SOUTH]])
    routes, _ = run(client)
    assert [r.source for r in routes] == ["fastest", "shortest", "via"]
    assert client.calls == ["fastest", "shortest", "eco", "via", "via"]


def test_reports_when_fewer_than_three_exist():
    client = FakeClient(
        main=[STRAIGHT],
        by_type={"shortest": [STRAIGHT_COPY], "eco": [STRAIGHT]},
        via=[[STRAIGHT_COPY], [STRAIGHT]],
    )
    routes, notes = run(client)
    assert len(routes) == 1
    assert "Only 1 distinct route" in notes[0]


def test_no_route_on_main_request_propagates():
    client = FakeClient(main=NoRouteFound("x"))
    with pytest.raises(NoRouteFound):
        run(client)


class TestToPlanned:
    def test_progress_indexes_map_to_our_miles(self):
        # Three equal segments; TomTom says the first point-to-point takes 2/3 of the time.
        route = raw((0, 0), (1, 0), (2, 0), (3, 0), seconds=900, progress=[(0, 0), (1, 600)])
        planned = to_planned(route, "fastest")
        one_third = planned.distance_mi / 3
        assert planned.profile.seconds_at(one_third) == pytest.approx(600)
        assert planned.profile.seconds_at(planned.distance_mi) == pytest.approx(900)

    def test_without_progress_falls_back_to_proportional(self):
        planned = to_planned(raw((0, 0), (1, 0), seconds=1000), "fastest")
        assert planned.profile.seconds_at(planned.distance_mi / 2) == pytest.approx(500)
