"""Tests for URL validation and SSRF protection."""

from unittest.mock import patch

import pytest

from app.fetcher import (
    URLValidationError,
    ValidatedURL,
    _pinned_request_url,
    validate_url,
)


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/recipe",
        "http://127.0.0.1/recipe",
        "http://0.0.0.0/recipe",
        "http://10.0.0.1/recipe",
        "http://192.168.1.1/recipe",
        "http://169.254.169.254/latest/meta-data",
        "ftp://example.com/recipe",
        "not-a-url",
        "http://example.com:6379/recipe",
    ],
)
def test_validate_url_rejects_unsafe(url):
    with pytest.raises(URLValidationError):
        validate_url(url)


@patch(
    "app.fetcher.socket.getaddrinfo",
    return_value=[(2, 1, 6, "", ("93.184.216.34", 443))],
)
def test_validate_url_accepts_public_https(_mock_getaddrinfo):
    result = validate_url("https://example.com/recipe")
    assert isinstance(result, ValidatedURL)
    assert result.url == "https://example.com/recipe"
    assert result.hostname == "example.com"
    assert result.ips == ("93.184.216.34",)


@patch(
    "app.fetcher.socket.getaddrinfo",
    return_value=[(2, 1, 6, "", ("93.184.216.34", 443))],
)
def test_pinned_request_url_uses_resolved_ip(_mock_getaddrinfo):
    target = validate_url("https://example.com/recipe")
    pinned = _pinned_request_url(target, "93.184.216.34")
    assert pinned.startswith("https://93.184.216.34/")
    assert "example.com" not in pinned
