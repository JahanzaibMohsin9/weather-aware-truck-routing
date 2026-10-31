import pytest


@pytest.fixture(autouse=True)
def no_retry_sleep(monkeypatch):
    """Retries back off with time.sleep; tests shouldn't wait."""
    monkeypatch.setattr("routing.services.http.time.sleep", lambda seconds: None)
