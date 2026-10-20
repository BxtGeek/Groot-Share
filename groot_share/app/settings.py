"""Application configuration loaded from environment variables."""
from __future__ import annotations

import os
from pathlib import Path


def _env_str(name: str, default: str) -> str:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "yes", "true", "on"}


APP_NAME = _env_str("APP_NAME", "Groot Share")
APP_TAGLINE = _env_str("APP_TAGLINE", "Your files. Your shares. Your control.")
APP_HOST = _env_str("APP_HOST", "0.0.0.0")
APP_PORT = _env_int("APP_PORT", 8080)

CONFIG_PATH = Path(_env_str("CONFIG_PATH", "/config/storages.json"))
MAX_UPLOAD_SIZE_MB = max(1, _env_int("MAX_UPLOAD_SIZE_MB", 2048))
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024

ADMIN_PASSWORD = _env_str("ADMIN_PASSWORD", "admin")
SESSION_SECRET = _env_str("SESSION_SECRET", "change-me")
SESSION_COOKIE_NAME = _env_str("SESSION_COOKIE_NAME", "groot_session")
SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", False)
SESSION_COOKIE_HTTPONLY = _env_bool("SESSION_COOKIE_HTTPONLY", True)
SESSION_COOKIE_SAMESITE = _env_bool("SESSION_COOKIE_SAMESITE", "Lax")

# Explicitly permitted container mount roots. Storage paths must live under one
# of these prefixes. This is the primary defense against arbitrary host paths.
PERMITTED_ROOTS = [
    Path(p).resolve() for p in _env_str("PERMITTED_ROOTS", "/storage").split(":") if p
]

# Where user uploads are staged before being moved into a storage root.
UPLOAD_TMP_ROOT = Path(_env_str("UPLOAD_TMP_ROOT", "/tmp/groot_uploads"))

# Allowed origins for the simple CSRF-safe cookie auth (informational only).
CORS_ORIGINS = [o for o in _env_str("CORS_ORIGINS", "").split(",") if o]

# Rate limiting for login attempts.
LOGIN_MAX_ATTEMPTS = _env_int("LOGIN_MAX_ATTEMPTS", 10)
LOGIN_LOCKOUT_SECONDS = _env_int("LOGIN_LOCKOUT_SECONDS", 300)