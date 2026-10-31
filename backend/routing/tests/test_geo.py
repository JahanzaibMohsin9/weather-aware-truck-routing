from datetime import datetime, timedelta, timezone

import pytest

from routing.domain.geo import (
    MILES_PER_DEGREE_LAT,
    TimeProfile,
    bearing_deg,
    build_checkpoints,
    checkpoint_miles,
    coverage_miles,
    cumulative_miles,
    haversine_mi,
    offset_point,
    point_at_mile,
    resample,
    shared_fraction,
    simplify,
)

DEPARTURE = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)


def north_line(miles: float, lng: float = 0.0, start_lat: float = 0.0):
    """A straight north-going route of known length."""
    return [(start_lat, lng), (start_lat + miles / MILES_PER_DEGREE_LAT, lng)]


class TestDistances:
    def test_one_degree_of_latitude(self):
        assert haversine_mi((0, 0), (1, 0)) == pytest.approx(69.09, abs=0.01)

    def test_dallas_to_denver_great_circle(self):
        assert haversine_mi((32.7767, -96.7970), (39.7392, -104.9903)) == pytest.approx(663, abs=2)

    def test_cumulative_miles(self):
        points = [(0, 0), (1, 0), (2, 0)]
        cum = cumulative_miles(points)
        assert cum[0] == 0
        assert cum[2] == pytest.approx(2 * MILES_PER_DEGREE_LAT)

    def test_point_at_mile_interpolates_and_clamps(self):
        points = north_line(100)
        cum = cumulative_miles(points)
        assert point_at_mile(points, cum, 50)[0] == pytest.approx(50 / MILES_PER_DEGREE_LAT)
        assert point_at_mile(points, cum, -5) == points[0]
        assert point_at_mile(points, cum, 500) == points[-1]

    def test_bearings(self):
        assert bearing_deg((0, 0), (1, 0)) == pytest.approx(0)
        assert bearing_deg((0, 0), (0, 1)) == pytest.approx(90)

    def test_offset_point_round_trip(self):
        lat, lng = offset_point((40, -100), 90, 30)
        assert haversine_mi((40, -100), (lat, lng)) == pytest.approx(30, abs=0.01)
        assert lng > -100

    def test_resample_spacing(self):
        samples = resample(north_line(10), 1)
        assert len(samples) == 11
        assert haversine_mi(samples[0], samples[1]) == pytest.approx(1, abs=1e-6)


class TestSimplify:
    def test_drops_collinear_points(self):
        line = [(0, k / 10) for k in range(11)]
        assert simplify(line, 1e-6) == [(0, 0), (0, 1)]

    def test_keeps_corners(self):
        corner = [(0, 0), (0, 0.5), (0, 1), (0.5, 1), (1, 1)]
        assert simplify(corner, 1e-6) == [(0, 0), (0, 1), (1, 1)]

    def test_keeps_deviation_above_tolerance_only(self):
        wiggle = [(0, 0), (0.0001, 0.5), (0, 1)]
        assert simplify(wiggle, 0.001) == [(0, 0), (0, 1)]
        assert simplify(wiggle, 0.00001) == wiggle


class TestCheckpointMiles:
    @pytest.mark.parametrize(
        "total, interval, expected",
        [
            (55, 25, [0, 25, 50, 55]),
            (50, 25, [0, 25, 50]),
            (10, 25, [0, 10]),
            (100, 10, [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]),
        ],
    )
    def test_spacing(self, total, interval, expected):
        assert checkpoint_miles(total, interval) == pytest.approx(expected)

    def test_float_noise_does_not_duplicate_destination(self):
        assert checkpoint_miles(50.0000000001, 25) == pytest.approx([0, 25, 50.0000000001])

    def test_rejects_non_positive_interval(self):
        with pytest.raises(ValueError):
            checkpoint_miles(100, 0)


class TestTimeProfile:
    def test_proportional(self):
        profile = TimeProfile.proportional(100, 7200)
        assert profile.seconds_at(25) == pytest.approx(1800)

    def test_knots_give_uneven_speed(self):
        # 50 mi in the first hour, the next 50 mi in 30 minutes
        profile = TimeProfile.from_knots([(50, 3600), (100, 5400)])
        assert profile.seconds_at(25) == pytest.approx(1800)
        assert profile.seconds_at(75) == pytest.approx(4500)
        assert profile.seconds_at(200) == 5400

    def test_decreasing_time_is_rejected(self):
        with pytest.raises(ValueError):
            TimeProfile.from_knots([(10, 600), (20, 500)])


class TestBuildCheckpoints:
    def test_count_spacing_and_etas(self):
        points = north_line(100)
        checkpoints = build_checkpoints(points, 25, TimeProfile.proportional(100, 7200), DEPARTURE)

        assert [cp.mile for cp in checkpoints] == pytest.approx([0, 25, 50, 75, 100])
        assert checkpoints[2].lat == pytest.approx(50 / MILES_PER_DEGREE_LAT)
        assert checkpoints[2].eta == DEPARTURE + timedelta(hours=1)
        assert checkpoints[-1].eta == DEPARTURE + timedelta(hours=2)

    def test_uses_profile_not_straight_proportion(self):
        points = north_line(100)
        profile = TimeProfile.from_knots([(50, 3600), (100, 5400)])
        checkpoints = build_checkpoints(points, 50, profile, DEPARTURE)
        assert [cp.eta - DEPARTURE for cp in checkpoints] == [
            timedelta(0),
            timedelta(hours=1),
            timedelta(hours=1, minutes=30),
        ]


class TestCoverage:
    def test_nearest_checkpoint_split(self):
        assert coverage_miles([0, 25, 50, 55]) == pytest.approx([12.5, 25, 15, 2.5])

    def test_lengths_sum_to_route_distance(self):
        miles = checkpoint_miles(812.4, 25)
        assert sum(coverage_miles(miles)) == pytest.approx(812.4)

    def test_destination_gets_mileage(self):
        assert coverage_miles([0, 10])[-1] == pytest.approx(5)

    def test_degenerate(self):
        assert coverage_miles([]) == []
        assert coverage_miles([0.0]) == [0.0]


class TestSharedFraction:
    def test_identical(self):
        route = [(40, -100), (40, -99), (40, -98)]
        assert shared_fraction(route, route) == pytest.approx(1)

    def test_parallel_routes_apart(self):
        a = [(40, -100), (40, -98)]
        b = [(40.1, -100), (40.1, -98)]  # ~7 miles north
        assert shared_fraction(a, b) == 0

    def test_tiny_offset_counts_as_same_road(self):
        a = [(40, -100), (40, -98)]
        b = [(40.001, -100), (40.001, -98)]  # ~0.07 miles
        assert shared_fraction(a, b) == pytest.approx(1)

    def test_half_shared(self):
        a = [(40, -100), (40, -99), (40, -98)]
        b = [(40, -100), (40, -99), (41, -98)]
        assert shared_fraction(a, b) == pytest.approx(0.5, abs=0.03)

    def test_sparse_vertices_still_overlap(self):
        # Same road, but one route has a vertex only at each end.
        dense = [(40, -100 + k / 10) for k in range(21)]
        sparse = [(40, -100), (40, -98)]
        assert shared_fraction(dense, sparse) == pytest.approx(1)
