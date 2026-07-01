"""Tests for environment configuration helpers."""

from app.config import env_list


def test_env_list_trims_whitespace(monkeypatch):
    monkeypatch.setenv("TEST_LIST", "https://a.example.com, https://b.example.com")
    assert env_list("TEST_LIST") == [
        "https://a.example.com",
        "https://b.example.com",
    ]
