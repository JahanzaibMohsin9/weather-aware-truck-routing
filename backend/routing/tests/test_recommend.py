import pytest

from routing.domain.levels import Level
from routing.domain.recommend import RouteSummary, rank, recommend, summarize

L, M, H, S, N = Level.LOW, Level.MODERATE, Level.HIGH, Level.SEVERE, Level.NO_TRAVEL


def summary(severe=0.0, high=0.0, avg=0.0, minutes=600.0, no_travel=False, complete=True):
    return RouteSummary(
        no_travel_mi=10.0 if no_travel else 0.0,
        severe_mi=severe,
        high_mi=high,
        no_forecast_mi=0.0 if complete else 25.0,
        avg_risk=avg,
        has_no_travel=no_travel,
        forecast_complete=complete,
        duration_s=minutes * 60,
    )


class TestSummarize:
    def test_nearest_checkpoint_mileage(self):
        # Checkpoints at 0, 25, 50, 55 cover 12.5, 25, 15 and 2.5 miles.
        result = summarize([0, 25, 50, 55], [L, S, H, L], duration_s=3600)
        assert result.severe_mi == pytest.approx(25)
        assert result.high_mi == pytest.approx(15)
        assert result.avg_risk == pytest.approx((25 * 3 + 15 * 2) / 55)
        assert not result.has_no_travel
        assert result.forecast_complete

    def test_no_travel_at_destination_is_flagged(self):
        result = summarize([0, 25, 50], [L, L, N], duration_s=3600)
        assert result.has_no_travel
        assert result.no_travel_mi == pytest.approx(12.5)

    def test_missing_forecast_is_tracked_not_scored(self):
        # Last checkpoint has no forecast: its miles count as no_forecast, not Low.
        result = summarize([0, 25, 50], [H, H, None], duration_s=3600)
        assert not result.forecast_complete
        assert result.no_forecast_mi == pytest.approx(12.5)
        assert result.avg_risk == pytest.approx(2.0)  # over the 37.5 covered miles only

    def test_no_forecast_anywhere(self):
        result = summarize([0, 25], [None, None], duration_s=3600)
        assert result.avg_risk is None


class TestRank:
    def test_fewest_severe_miles_first(self):
        assert rank([summary(severe=25), summary(severe=0)]) == [1, 0]

    def test_then_fewest_high_miles(self):
        assert rank([summary(high=50), summary(high=10)]) == [1, 0]

    def test_then_lowest_average_risk(self):
        assert rank([summary(avg=0.9), summary(avg=0.4)]) == [1, 0]

    def test_then_shortest_time(self):
        assert rank([summary(minutes=700), summary(minutes=650)]) == [1, 0]

    def test_risk_beats_time(self):
        # Lower average risk wins even when much slower.
        assert rank([summary(avg=0.824, minutes=500), summary(avg=0.821, minutes=900)]) == [1, 0]

    def test_float_noise_falls_through_to_time(self):
        assert rank([summary(avg=0.5 + 1e-12, minutes=500), summary(avg=0.5, minutes=900)]) == [0, 1]

    def test_severe_beats_high(self):
        assert rank([summary(severe=1, high=0), summary(severe=0, high=500)]) == [1, 0]

    def test_no_travel_ranks_last(self):
        assert rank([summary(no_travel=True), summary(severe=300, minutes=900)]) == [1, 0]

    def test_incomplete_forecast_ranks_after_complete(self):
        assert rank([summary(complete=False), summary(severe=100)]) == [1, 0]

    def test_no_travel_ranks_after_incomplete(self):
        assert rank([summary(no_travel=True), summary(complete=False)]) == [1, 0]

    def test_stable_for_identical_routes(self):
        assert rank([summary(), summary(), summary()]) == [0, 1, 2]


class TestRecommend:
    def test_explains_severe_difference(self):
        index, text = recommend([summary(severe=25, minutes=600), summary(severe=0, minutes=618)], ["A", "B"])
        assert index == 1
        assert text == "Route B: 0 severe miles vs 25 on Route A; 18 min longer."

    def test_explains_time_tiebreak(self):
        index, text = recommend([summary(minutes=600), summary(minutes=630)], ["A", "B"])
        assert index == 0
        assert text == "Route A: same weather risk as Route B and 30 min faster."

    def test_full_tie(self):
        index, text = recommend([summary(), summary()], ["A", "B"])
        assert index == 0
        assert text == "Route A: same weather risk and travel time as Route B."

    def test_all_no_travel_recommends_none(self):
        index, text = recommend([summary(no_travel=True), summary(no_travel=True)], ["A", "B"])
        assert index is None
        assert "No Travel" in text

    def test_single_route(self):
        index, text = recommend([summary()], ["A"])
        assert index == 0
        assert text == "Route A is the only route available."

    def test_avoids_no_travel(self):
        index, text = recommend([summary(no_travel=True), summary(severe=50)], ["A", "B"])
        assert index == 1
        assert text.startswith("Route B avoids the No Travel conditions on Route A")
