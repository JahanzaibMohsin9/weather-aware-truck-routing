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
# Render sets this to the service's public hostname.
if os.environ.get("RENDER_EXTERNAL_HOSTNAME"):
    ALLOWED_HOSTS.append(os.environ["RENDER_EXTERNAL_HOSTNAME"])

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
    "django.middleware.gzip.GZipMiddleware",
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

# Hostnames without a scheme are taken as https (Render passes bare hostnames).
CORS_ALLOWED_ORIGINS = [
    origin if "://" in origin else f"https://{origin}"
    for origin in env_list("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "UNAUTHENTICATED_USER": None,
}

# Behind the host's HTTPS proxy.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
if not DEBUG:
    SECURE_HSTS_SECONDS = 31_536_000

SILENCED_SYSTEM_CHECKS = [
    # No cookies or sessions: the API is stateless JSON, so there is nothing for CSRF to protect.
    "security.W003",
    # Render's edge redirects HTTP to HTTPS; redirecting here too would break its internal health check.
    "security.W008",
    # HSTS subdomain and preload policy belong to the parent domain (onrender.com), which isn't ours.
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
