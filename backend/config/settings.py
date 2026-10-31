"""Django settings. Everything deployment-specific comes from environment
variables (see .env.example); a local .env file is loaded if present."""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


# Off unless explicitly turned on, so a missing variable never exposes debug pages.
DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() == "true"

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is off.")
    SECRET_KEY = "dev-only-insecure-key"

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")
# Heroku sets DYNO on every dyno; the app is served from <app-name>.herokuapp.com.
if "DYNO" in os.environ:
    ALLOWED_HOSTS.append(".herokuapp.com")

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "routing",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    # Heatmap responses are ~200 KB of repetitive numbers; gzip shrinks them ~7x.
    # Listed before WhiteNoise so the frontend files it serves are compressed too.
    "django.middleware.gzip.GZipMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# The app stores nothing; all data comes from external APIs.
DATABASES = {}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        # One trip plus its heatmap is ~310 forecast locations, more than the
        # default 300 entries. A cached forecast is ~17 KB, so 2,000 is ~35 MB.
        "OPTIONS": {"MAX_ENTRIES": 2000},
    }
}

TIME_ZONE = "UTC"
USE_TZ = True
STATIC_URL = "static/"
# Heroku's Python buildpack runs collectstatic when it finds manage.py; this gives it a target.
STATIC_ROOT = BASE_DIR / "staticfiles"

# In production Django also serves the built React app (frontend/dist) at the
# site root, so the page and the API share one origin and need no CORS.
FRONTEND_DIST = BASE_DIR.parent / "frontend" / "dist"
WHITENOISE_ROOT = FRONTEND_DIST if FRONTEND_DIST.is_dir() else None
WHITENOISE_INDEX_FILE = True


def _vite_hashed_asset(path: str, url: str) -> bool:
    # Vite puts a content hash in every file name under /assets/, so they never change.
    return url.startswith("/assets/")


WHITENOISE_IMMUTABLE_FILE_TEST = _vite_hashed_asset

# Only needed for local development, where Vite serves the page on another port.
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:5173")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "UNAUTHENTICATED_USER": None,
}

# Heroku's router terminates HTTPS and says so in X-Forwarded-Proto.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
if not DEBUG:
    # herokuapp.com answers plain HTTP too, so redirect it here.
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31_536_000

SILENCED_SYSTEM_CHECKS = [
    # No cookies or sessions: the API is stateless JSON, so there is nothing for CSRF to protect.
    "security.W003",
    # HSTS subdomain and preload policy belong to the parent domain (herokuapp.com), which isn't ours.
    "security.W005",
    "security.W021",
]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}

TOMTOM_API_KEY = os.environ.get("TOMTOM_API_KEY", "")
