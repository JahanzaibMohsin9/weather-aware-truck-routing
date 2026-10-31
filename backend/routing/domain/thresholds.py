"""Every number from the brief's risk table and load rules, in one place.

Each scale lists the value at which a band starts. A value equal to a band's
start belongs to that band. No Travel starts *above* the rain and snow
maximums ("> 1.00", "> 3.0"), so Severe includes them; for wind it starts *at*
55 mph ("≥ 55"). See docs/risk-model.md.
"""

from dataclasses import dataclass

from .levels import Level


@dataclass(frozen=True)
class Scale:
    name: str
    unit: str
    moderate_from: float
    high_from: float
    severe_from: float
    no_travel_from: float
    no_travel_inclusive: bool  # True: value >= no_travel_from; False: value > no_travel_from


WIND_MPH = Scale("Wind", "mph", 25, 35, 45, 55, no_travel_inclusive=True)
RAIN_IN_HR = Scale("Rain", "in/hr", 0.10, 0.25, 0.50, 1.00, no_travel_inclusive=False)
SNOW_IN_HR = Scale("Snow", "in/hr", 0.5, 1.0, 2.0, 3.0, no_travel_inclusive=False)


@dataclass(frozen=True)
class LoadRule:
    """Wind in [wind_from, wind_below) with a load over `load_over_lbs` is at least `level`."""

    wind_from: float
    wind_below: float
    load_over_lbs: float
    level: Level


# ">= 55 mph -> No Travel for any load" is already the wind scale's No Travel band.
LOAD_RULES = (
    LoadRule(wind_from=45, wind_below=55, load_over_lbs=30_000, level=Level.NO_TRAVEL),
    LoadRule(wind_from=35, wind_below=45, load_over_lbs=40_000, level=Level.SEVERE),
)
