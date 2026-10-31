"""Forecast window shared by input validation and weather requests."""

from datetime import datetime, timedelta, timezone

FORECAST_DAYS = 16
SLIDER_HOURS = 48


def start_limit(now: datetime) -> datetime:
    """Exclusive latest departure supporting every slider frame.

    Forecast days start at UTC midnight. Precipitation for the final frame
    needs the following hourly timestamp, also inside the forecast window.
    """
    midnight = now.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight + timedelta(days=FORECAST_DAYS, hours=-(SLIDER_HOURS + 1))
