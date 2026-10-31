"""Route summaries, ranking and the one-line reason for the pick.

Ranking keys, in order (see docs/risk-model.md):
  1. has a No Travel checkpoint      (added: the brief doesn't rank No Travel)
  2. has a checkpoint with no forecast (added: unknown is not safe)
  3. fewest Severe miles             \
  4. fewest High miles                | the brief's preference order
  5. lowest average risk              |
  6. shortest travel time            /
Values are compared unrounded; floats within 1e-9 count as equal.
"""

from __future__ import annotations

import functools
import math
from dataclasses import dataclass
from typing import Sequence

from .geo import coverage_miles
from .levels import Level

TOLERANCE = 1e-9


@dataclass(frozen=True)
class RouteSummary:
    no_travel_mi: float
    severe_mi: float
    high_mi: float
    no_forecast_mi: float
    avg_risk: float | None  # None when no checkpoint has a forecast
    has_no_travel: bool
    forecast_complete: bool
    duration_s: float


def summarize(miles: Sequence[float], levels: Sequence[Level | None], duration_s: float) -> RouteSummary:
    """`levels[i]` is checkpoint i's level, or None when it has no forecast."""
    totals = {level: 0.0 for level in Level}
    no_forecast = 0.0
    for covered, level in zip(coverage_miles(miles), levels):
        if level is None:
            no_forecast += covered
        else:
            totals[level] += covered
    forecast_miles = sum(totals.values())
    avg = sum(level * mi for level, mi in totals.items()) / forecast_miles if forecast_miles else None
    return RouteSummary(
        no_travel_mi=totals[Level.NO_TRAVEL],
        severe_mi=totals[Level.SEVERE],
        high_mi=totals[Level.HIGH],
        no_forecast_mi=no_forecast,
        avg_risk=avg,
        has_no_travel=any(level == Level.NO_TRAVEL for level in levels),
        forecast_complete=all(level is not None for level in levels),
        duration_s=duration_s,
    )


def _keys(s: RouteSummary) -> tuple[float, ...]:
    return (
        float(s.has_no_travel),
        float(not s.forecast_complete),
        s.severe_mi,
        s.high_mi,
        math.inf if s.avg_risk is None else s.avg_risk,
        s.duration_s,
    )


def _compare(a: RouteSummary, b: RouteSummary) -> int:
    for x, y in zip(_keys(a), _keys(b)):
        if not math.isclose(x, y, rel_tol=0, abs_tol=TOLERANCE):
            return -1 if x < y else 1
    return 0


def rank(summaries: Sequence[RouteSummary]) -> list[int]:
    """Route indexes, best first. Equal routes keep their original order."""
    key = functools.cmp_to_key(lambda i, j: _compare(summaries[i], summaries[j]))
    return sorted(range(len(summaries)), key=key)


def recommend(summaries: Sequence[RouteSummary], ids: Sequence[str]) -> tuple[int | None, str]:
    """The index of the recommended route (None if none is drivable) and why."""
    order = rank(summaries)
    best = summaries[order[0]]
    if best.has_no_travel:
        return None, (
            "Every route has a No Travel segment, so none is recommended. "
            "Consider delaying departure."
        )
    name = f"Route {ids[order[0]]}"
    if len(order) == 1:
        text = f"{name} is the only route available."
    else:
        text = _explain(name, best, f"Route {ids[order[1]]}", summaries[order[1]])
    if not best.forecast_complete:
        text += f" The forecast doesn't cover the last {_miles(best.no_forecast_mi)} mi of it."
    return order[0], text


def _explain(name: str, w: RouteSummary, other: str, r: RouteSummary) -> str:
    def differs(x: float, y: float) -> bool:
        return not math.isclose(x, y, rel_tol=0, abs_tol=TOLERANCE)

    if r.has_no_travel:
        reason = f"{name} avoids the No Travel conditions on {other}"
    elif not r.forecast_complete and w.forecast_complete:
        reason = f"{name} has a full forecast; {other} has {_miles(r.no_forecast_mi)} mi without one"
    elif differs(w.severe_mi, r.severe_mi):
        reason = f"{name}: {_miles(w.severe_mi)} severe miles vs {_miles(r.severe_mi)} on {other}"
    elif differs(w.high_mi, r.high_mi):
        reason = (
            f"{name}: same severe miles, {_miles(w.high_mi)} high miles "
            f"vs {_miles(r.high_mi)} on {other}"
        )
    elif w.avg_risk is not None and r.avg_risk is not None and differs(w.avg_risk, r.avg_risk):
        reason = (
            f"{name}: same severe and high miles, lower average risk "
            f"({w.avg_risk:.2f} vs {r.avg_risk:.2f} on {other})"
        )
    elif r.duration_s - w.duration_s >= 60:
        return f"{name}: same weather risk as {other} and {_duration(r.duration_s - w.duration_s)} faster."
    else:
        return f"{name}: same weather risk and travel time as {other}."

    delta = w.duration_s - r.duration_s
    if abs(delta) >= 60:
        reason += f"; {_duration(abs(delta))} {'longer' if delta > 0 else 'faster'}"
    return reason + "."


def _miles(value: float) -> str:
    return f"{value:.0f}" if value == 0 or value >= 10 else f"{value:.1f}"


def _duration(seconds: float) -> str:
    minutes = round(seconds / 60)
    if minutes < 60:
        return f"{minutes} min"
    return f"{minutes // 60} h {minutes % 60} min"
