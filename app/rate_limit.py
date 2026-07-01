"""Rate limiting configuration."""

from starlette.requests import Request

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import TRUST_PROXY_HEADERS


def get_client_ip(request: Request) -> str:
    if TRUST_PROXY_HEADERS:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

    return get_remote_address(request)


limiter = Limiter(key_func=get_client_ip, default_limits=[])
