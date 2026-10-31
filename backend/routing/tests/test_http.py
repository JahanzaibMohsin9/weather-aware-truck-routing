"""Retries and the per-request time budget. time.sleep is patched out (conftest)."""

import time

import pytest
import requests

from routing.services.http import OutOfTime, get_with_retry


class Response:
    def __init__(self, status_code):
        self.status_code = status_code


class Session:
    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.timeouts = []

    def get(self, url, params, timeout):
        self.timeouts.append(timeout)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return Response(outcome)


def get(session, deadline=None):
    return get_with_retry(session, "https://example.test", params={}, timeout=20, deadline=deadline)


def test_no_budget_uses_the_full_timeout():
    session = Session(200)
    assert get(session).status_code == 200
    assert session.timeouts == [20]


def test_call_gets_at_most_the_time_left():
    session = Session(200)
    get(session, deadline=time.monotonic() + 5)
    assert session.timeouts[0] == pytest.approx(5, abs=0.5)


def test_retries_a_temporary_error_when_there_is_time():
    session = Session(503, 200)
    assert get(session, deadline=time.monotonic() + 20).status_code == 200
    assert len(session.timeouts) == 2


def test_no_retry_when_too_little_time_is_left():
    session = Session(503, 200)
    assert get(session, deadline=time.monotonic() + 2).status_code == 503
    assert len(session.timeouts) == 1


def test_network_error_without_time_to_retry_is_raised():
    session = Session(requests.ConnectionError(), 200)
    with pytest.raises(requests.ConnectionError):
        get(session, deadline=time.monotonic() + 2)


def test_budget_already_used_up():
    session = Session(200)
    with pytest.raises(OutOfTime):
        get(session, deadline=time.monotonic() + 0.5)
    assert session.timeouts == []


def test_out_of_time_is_a_timeout():
    # Clients map requests.Timeout to ProviderTimeout (HTTP 504).
    assert issubclass(OutOfTime, requests.Timeout)
