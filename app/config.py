"""Environment-driven application configuration."""

import os


def env_flag(name: str, *, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.lower() in ("1", "true", "yes")


def env_list(name: str, *, default: str = "*") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


def env_int(name: str, *, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return int(raw)


def env_float(name: str, *, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return float(raw)


ALLOWED_ORIGINS = env_list("ALLOWED_ORIGINS", default="*")
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", default="*")
OPENAPI_DOCS = env_flag("OPENAPI_DOCS", default=False)
TRUST_PROXY_HEADERS = env_flag("TRUST_PROXY_HEADERS", default=False)
EXTRACT_TIMEOUT_SECONDS = env_float("EXTRACT_TIMEOUT", default=15.0)
MAX_CONCURRENT_FETCHES = env_int("MAX_CONCURRENT_FETCHES", default=5)
ALLOWED_FETCH_PORTS = {
    int(port)
    for port in env_list("ALLOWED_FETCH_PORTS", default="80,443")
}
