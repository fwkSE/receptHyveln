"""URL validation and safe HTTP fetching with SSRF protection."""

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx

from app.config import ALLOWED_FETCH_PORTS, MAX_CONCURRENT_FETCHES

USER_AGENT = "ReceptHyveln/1.0"
MAX_BODY_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 5
FETCH_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
_fetch_semaphore = asyncio.Semaphore(MAX_CONCURRENT_FETCHES)

PRIVATE_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


class URLValidationError(ValueError):
    pass


class FetchError(Exception):
    pass


@dataclass(frozen=True)
class ValidatedURL:
    url: str
    hostname: str
    port: int
    ips: tuple[str, ...]


def _is_private_ip(ip_str: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return True
    if (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    ):
        return True
    return any(addr in network for network in PRIVATE_NETWORKS)


def _resolve_public_ips(hostname: str, port: int) -> tuple[str, ...]:
    try:
        addr_infos = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise URLValidationError("Kunde inte slå upp värdnamnet.") from exc

    ips: list[str] = []
    for info in addr_infos:
        ip = info[4][0]
        if _is_private_ip(ip):
            raise URLValidationError("Den här adressen är inte tillåten.")
        if ip not in ips:
            ips.append(ip)

    if not ips:
        raise URLValidationError("Kunde inte slå upp värdnamnet.")

    return tuple(ips)


def validate_url(url: str) -> ValidatedURL:
    """Validate URL scheme, hostname, port, and resolved IPs."""
    parsed = urlparse(url.strip())

    if parsed.scheme not in ("http", "https"):
        raise URLValidationError("Endast http- och https-URL:er stöds.")

    if not parsed.hostname:
        raise URLValidationError("Ogiltig URL.")

    hostname = parsed.hostname.lower().rstrip(".")
    if hostname in ("localhost", "0.0.0.0"):
        raise URLValidationError("Den här adressen är inte tillåten.")

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if port not in ALLOWED_FETCH_PORTS:
        raise URLValidationError("Den här porten är inte tillåten.")

    ips = _resolve_public_ips(hostname, port)

    return ValidatedURL(
        url=url.strip(),
        hostname=hostname,
        port=port,
        ips=ips,
    )


def _format_ip_for_url(ip: str) -> str:
    if ":" in ip and not ip.startswith("["):
        return f"[{ip}]"
    return ip


def _pinned_request_url(target: ValidatedURL, ip: str) -> str:
    parsed = urlparse(target.url)
    host = _format_ip_for_url(ip)
    default_port = 443 if parsed.scheme == "https" else 80
    netloc = f"{host}:{target.port}" if target.port != default_port else host
    return parsed._replace(netloc=netloc).geturl()


def _redirect_url(current_url: str, location: str) -> str:
    joined = urljoin(current_url, location)
    if not joined.startswith(("http://", "https://")):
        raise URLValidationError("Omdirigeringen är inte tillåten.")
    return joined


async def _fetch_once(client: httpx.AsyncClient, target: ValidatedURL) -> httpx.Response:
    request_headers = {
        "User-Agent": USER_AGENT,
        "Host": target.hostname,
    }
    extensions = {"sni_hostname": target.hostname}

    last_error: Exception | None = None
    for ip in target.ips:
        request_url = _pinned_request_url(target, ip)
        request = client.build_request(
            "GET",
            request_url,
            headers=request_headers,
            extensions=extensions,
        )
        try:
            return await client.send(request, stream=True)
        except httpx.HTTPError as exc:
            last_error = exc
            continue

    raise FetchError("Kunde inte hämta sidan.") from last_error


async def fetch_html(url: str) -> str:
    """Fetch HTML from a validated public URL with IP pinning."""
    async with _fetch_semaphore:
        current = validate_url(url)
        redirects = 0

        async with httpx.AsyncClient(
            follow_redirects=False,
            timeout=FETCH_TIMEOUT,
        ) as client:
            while True:
                response = await _fetch_once(client, current)

                if response.is_redirect:
                    location = response.headers.get("location")
                    await response.aclose()
                    if not location:
                        raise FetchError("Omdirigeringen saknar mål-URL.")

                    redirects += 1
                    if redirects > MAX_REDIRECTS:
                        raise FetchError("För många omdirigeringar.")

                    current = validate_url(_redirect_url(current.url, location))
                    continue

                try:
                    if response.status_code >= 400:
                        raise FetchError(
                            f"Sidan svarade med felkod {response.status_code}."
                        )

                    content = await response.aread()
                    if len(content) > MAX_BODY_BYTES:
                        raise FetchError("Sidan är för stor att läsa in.")

                    encoding = response.encoding or "utf-8"
                    return content.decode(encoding, errors="replace")
                finally:
                    await response.aclose()
