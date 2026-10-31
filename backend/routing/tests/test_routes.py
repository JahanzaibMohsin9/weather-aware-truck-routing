import time
from datetime import datetime, timezone

import pytest

from routing.services.errors import NoRouteFound, ProviderError, ProviderTimeout
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
    """Answers by request kind: main call, extra route types, via-point calls.

    Extra requests run in parallel, so via answers are keyed by which side of
    the east-going trip the via point is on, not by call order. The first
    side tried (+90° from east) is south.
    """

    def __init__(self, main, by_type=None, via=None, delays=None):
        self.main = main
        self.by_type = by_type or {}
        self.via = via or {}
        self.delays = delays or {}
        self.calls = []
        self.alternatives = []

    def calculate_routes(self, locations, *, load_lbs, depart_at, route_type="fastest", max_alternatives=0):
        self.alternatives.append(max_alternatives)
        if len(locations) == 3:
            kind = "south" if locations[1][0] < ORIGIN[0] else "north"
            self.calls.append("via")
            result = self.via.get(kind, [])
        else:
            kind = route_type
            self.calls.append(route_type)
            result = self.main if route_type == "fastest" else self.by_type.get(route_type, [])
        time.sleep(self.delays.get(kind, 0))
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


ALL_EXTRA_CALLS = sorted(["fastest", "shortest", "eco", "via", "via"])


def test_tops_up_with_route_types_then_via_and_drops_duplicates():
    client = FakeClient(
        main=[STRAIGHT, STRAIGHT_COPY],
        by_type={"shortest": [NORTH], "eco": [NORTH_COPY]},
        via={"south": [SOUTH]},
    )
    routes, notes = run(client)
    assert [r.source for r in routes] == ["fastest", "shortest", "via"]
    assert sorted(client.calls) == ALL_EXTRA_CALLS
    assert client.alternatives == [2] * 5
    assert notes == []


def test_priority_order_not_completion_order():
    # The shortest-route answer arrives last but still outranks the via route.
    client = FakeClient(
        main=[STRAIGHT],
        by_type={"shortest": [NORTH]},
        via={"south": [SOUTH]},
        delays={"shortest": 0.05},
    )
    routes, _ = run(client)
    assert [r.source for r in routes] == ["fastest", "shortest", "via"]


def test_existing_route_plus_detour_is_a_duplicate():
    # Seen live on Dallas -> Denver: a via route that was the fastest route plus a detour.
    client = FakeClient(main=[STRAIGHT, NORTH], via={"south": [STRAIGHT_WITH_DETOUR], "north": [SOUTH]})
    routes, _ = run(client)
    assert [r.source for r in routes] == ["fastest", "alternative", "via"]
    assert routes[2].points == SOUTH.points


def test_via_without_route_uses_other_side():
    client = FakeClient(
        main=[STRAIGHT], by_type={"shortest": [NORTH]}, via={"south": NoRouteFound("lake"), "north": [SOUTH]}
    )
    routes, _ = run(client)
    assert [r.source for r in routes] == ["fastest", "shortest", "via"]
    assert sorted(client.calls) == ALL_EXTRA_CALLS


def test_returns_fewer_routes_with_a_note_when_no_others_exist():
    # e.g. Key West -> Marathon: one road, and the sideways via points land in the sea.
    client = FakeClient(
        main=[STRAIGHT],
        by_type={"shortest": [STRAIGHT_COPY], "eco": [STRAIGHT]},
        via={"south": NoRouteFound("sea"), "north": [STRAIGHT]},
    )
    routes, notes = run(client)
    assert [r.source for r in routes] == ["fastest"]
    assert notes == [
        "Only 1 distinct truck route for this trip: every other option found was more than 90% the same road."
    ]
    assert sorted(client.calls) == ALL_EXTRA_CALLS


def test_note_is_plural_for_two_routes():
    _, notes = run(FakeClient(main=[STRAIGHT, NORTH]))
    assert notes[0].startswith("Only 2 distinct truck routes for this trip")


def test_alternatives_from_top_up_can_complete_the_comparison():
    routes, notes = run(FakeClient(main=[STRAIGHT], by_type={"shortest": [STRAIGHT_COPY, NORTH, SOUTH]}))
    assert len(routes) == 3
    assert notes == []


def test_optional_provider_failure_does_not_discard_complete_result():
    routes, _ = run(FakeClient(main=[STRAIGHT], by_type={"shortest": [NORTH, SOUTH], "eco": ProviderError("failed")}))
    assert len(routes) == 3


@pytest.mark.parametrize("error", [ProviderError("failed"), ProviderTimeout("slow")])
def test_failed_search_still_returns_routes_and_says_others_may_exist(error):
    routes, notes = run(FakeClient(main=[STRAIGHT], by_type={"shortest": error}))
    assert len(routes) == 1
    assert "Some searches for alternatives failed, so other routes may exist" in notes[0]


def test_empty_main_response_is_no_route():
    with pytest.raises(NoRouteFound):
        run(FakeClient(main=[]))


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
