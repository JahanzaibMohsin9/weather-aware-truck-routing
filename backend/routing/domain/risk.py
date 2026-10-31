"""Weather risk at a checkpoint: classify wind, rain and snow, take the worst,
then apply the load rules (which can only raise the level)."""

from __future__ import annotations

from dataclasses import dataclass, field

from .levels import Level
from .thresholds import LOAD_RULES, RAIN_IN_HR, SNOW_IN_HR, WIND_MPH, Scale

__all__ = ["Level", "Assessment", "assess", "classify", "classify_wind", "classify_rain", "classify_snow"]


def classify(value: float, scale: Scale) -> Level:
    no_travel = (
        value >= scale.no_travel_from if scale.no_travel_inclusive else value > scale.no_travel_from
    )
    if no_travel:
        return Level.NO_TRAVEL
    if value >= scale.severe_from:
        return Level.SEVERE
    if value >= scale.high_from:
        return Level.HIGH
    if value >= scale.moderate_from:
        return Level.MODERATE
    return Level.LOW


def classify_wind(mph: float) -> Level:
    return classify(mph, WIND_MPH)


def classify_rain(in_hr: float) -> Level:
    return classify(in_hr, RAIN_IN_HR)


def classify_snow(in_hr: float) -> Level:
    return classify(in_hr, SNOW_IN_HR)


@dataclass(frozen=True)
class Assessment:
    level: Level
    reasons: list[str] = field(default_factory=list)


def assess(*, wind_mph: float, rain_in_hr: float, snow_in_hr: float, load_lbs: float) -> Assessment:
    reasons = []
    level = Level.LOW
    for value, scale, shown in (
        (wind_mph, WIND_MPH, f"{wind_mph:g}"),
        (rain_in_hr, RAIN_IN_HR, f"{rain_in_hr:.2f}"),
        (snow_in_hr, SNOW_IN_HR, f"{snow_in_hr:.2f}"),
    ):
        condition_level = classify(value, scale)
        if condition_level > Level.LOW:
            reasons.append(f"{scale.name} {shown} {scale.unit}: {condition_level.label}")
        level = max(level, condition_level)

    for rule in LOAD_RULES:
        applies = rule.wind_from <= wind_mph < rule.wind_below and load_lbs > rule.load_over_lbs
        if applies and rule.level > level:
            level = rule.level
            reasons.append(
                f"Load {load_lbs:,.0f} lb over {rule.load_over_lbs:,.0f} lb in "
                f"{rule.wind_from:g}-{rule.wind_below - 1:g} mph wind: {rule.level.label}"
            )
    return Assessment(level, reasons)
