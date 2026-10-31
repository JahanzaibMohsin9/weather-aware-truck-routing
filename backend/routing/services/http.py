"""GET with one retry for temporary failures (rate limits, 5xx, network errors)."""

import time

import requests

RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})


def get_with_retry(
    session: requests.Session,
    url: str,
    *,
    params,
    timeout: float,
    attempts: int = 2,
    backoff_s: float = 0.8,
) -> requests.Response:
    """The response of the last attempt. Raises the network error if every attempt failed."""
    for attempt in range(1, attempts + 1):
        try:
            response = session.get(url, params=params, timeout=timeout)
        except requests.RequestException:
            if attempt == attempts:
                raise
        else:
            if response.status_code not in RETRY_STATUSES or attempt == attempts:
                return response
        time.sleep(backoff_s * attempt)
    raise AssertionError("unreachable")
