"""Settings for the test suite: runs without a .env file or any API keys."""

import os

os.environ.setdefault("DJANGO_DEBUG", "true")
os.environ.setdefault("DJANGO_SECRET_KEY", "test-only")

from .settings import *  # noqa: E402,F401,F403
