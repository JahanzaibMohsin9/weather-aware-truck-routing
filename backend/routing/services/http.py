"""GET with one retry for temporary failures (rate limits, 5xx, network errors),
inside an optional time budget for the whole user request."""

import time

import requests

RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
# Not worth starting (or retrying) a call with less time than this left.
MIN_USEFUL_S = 1.5


class OutOfTime(requests.Timeout):
    """The request's time budget ran out before this call could finish."""


def get_with_retry(
    session: requests.Session,
    url: str,
    *,
    params,
    timeout: float,
    deadline: float | None = None,
    attempts: int = 2,
    backoff_s: float = 0.8,
) -> requests.Response:
    """The response of the last attempt. Raises the network error if every
    attempt failed. `deadline` is a `time.monotonic()` value: each attempt gets
    at most the time left, and there is no retry once too little is left."""

    def time_left() -> float:
        return float("inf") if deadline is None else deadline - time.monotonic()

    for attempt in range(1, attempts + 1):
        if time_left() < MIN_USEFUL_S:
            raise OutOfTime("time budget used up")
        try:
            response = session.get(url, params=params, timeout=min(timeout, time_left()))
        except requests.RequestException:
            if attempt == attempts or time_left() < backoff_s * attempt + MIN_USEFUL_S:
                raise
        else:
            if (
                response.status_code not in RETRY_STATUSES
                or attempt == attempts
                or time_left() < backoff_s * attempt + MIN_USEFUL_S
            ):
                return response
        time.sleep(backoff_s * attempt)
    raise AssertionError("unreachable")
