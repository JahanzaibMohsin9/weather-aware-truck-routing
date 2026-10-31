"""Every boundary in the brief's risk table and load rules.

Boundary convention (see docs/risk-model.md): a value at a band's lower bound
belongs to that band; Severe includes its top value for rain and snow.
"""

import pytest

from routing.domain.risk import Level, assess, classify_rain, classify_snow, classify_wind

L, M, H, S, N = Level.LOW, Level.MODERATE, Level.HIGH, Level.SEVERE, Level.NO_TRAVEL


@pytest.mark.parametrize(
    "mph, expected",
    [
        (0, L), (24.9, L),
        (25, M), (34, M), (34.9, M),
        (35, H), (44.9, H),
        (45, S), (54.9, S),
        (55, N), (80, N),
    ],
)
def test_wind(mph, expected):
    assert classify_wind(mph) == expected


@pytest.mark.parametrize(
    "inches, expected",
    [
        (0, L), (0.0999, L),
        (0.10, M), (0.2499, M),
        (0.25, H), (0.4999, H),
        (0.50, S), (1.00, S),
        (1.0001, N), (1.01, N), (3, N),
    ],
)
def test_rain(inches, expected):
    assert classify_rain(inches) == expected


@pytest.mark.parametrize(
    "inches, expected",
    [
        (0, L), (0.49, L),
        (0.5, M), (0.99, M),
        (1.0, H), (1.99, H),
        (2.0, S), (3.0, S),
        (3.01, N), (6, N),
    ],
)
def test_snow(inches, expected):
    assert classify_snow(inches) == expected


class TestCheckpointLevel:
    def test_calm(self):
        result = assess(wind_mph=5, rain_in_hr=0, snow_in_hr=0, load_lbs=20000)
        assert result.level == L
        assert result.reasons == []

    def test_highest_condition_wins(self):
        result = assess(wind_mph=10, rain_in_hr=0.12, snow_in_hr=2.5, load_lbs=10000)
        assert result.level == S
        assert result.reasons == ["Rain 0.12 in/hr: Moderate", "Snow 2.50 in/hr: Severe"]


class TestLoadRules:
    @pytest.mark.parametrize(
        "mph, load, expected",
        [
            # 45-54 mph: over 30,000 lb is No Travel
            (47, 30000, S),
            (47, 30001, N),
            (45, 30001, N),
            (54.9, 30001, N),
            # 35-44 mph: over 40,000 lb is Severe
            (40, 40000, H),
            (40, 40001, S),
            (35, 40001, S),
            (44.9, 40001, S),
            # outside the wind bands the load doesn't matter
            (34.9, 80000, M),
            # >= 55 mph is No Travel for any load
            (55, 1000, N),
            (60, 1, N),
        ],
    )
    def test_levels(self, mph, load, expected):
        assert assess(wind_mph=mph, rain_in_hr=0, snow_in_hr=0, load_lbs=load).level == expected

    def test_45_to_54_with_light_load_stays_severe(self):
        # The 35-44 mph rule (> 40,000 lb) must not leak into the next band.
        assert assess(wind_mph=50, rain_in_hr=0, snow_in_hr=0, load_lbs=45000).level == N
        assert assess(wind_mph=50, rain_in_hr=0, snow_in_hr=0, load_lbs=20000).level == S

    def test_load_rules_never_lower_the_level(self):
        # Heavy snow is already No Travel; a wind load rule giving Severe must not lower it.
        result = assess(wind_mph=40, rain_in_hr=0, snow_in_hr=4, load_lbs=45000)
        assert result.level == N

    def test_reason_explains_the_load_rule(self):
        result = assess(wind_mph=47, rain_in_hr=0, snow_in_hr=0, load_lbs=34000)
        assert result.reasons == [
            "Wind 47 mph: Severe",
            "Load 34,000 lb over 30,000 lb in 45-54 mph wind: No Travel",
        ]

    def test_no_load_reason_when_it_changes_nothing(self):
        result = assess(wind_mph=60, rain_in_hr=0, snow_in_hr=0, load_lbs=50000)
        assert result.reasons == ["Wind 60 mph: No Travel"]
