"""Smoke checks reject broken contracts without network calls."""

import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest

spec = importlib.util.spec_from_file_location(
    "smoke", Path(__file__).resolve().parents[3] / "scripts/verify-deployment.py"
)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def healthy(url):
    if url.startswith("http:"):
        return 307, {"Location": url.replace("http:", "https:")}, b""
    if "health-check" in url:
        return 200, {}, b"true"
    if "users/me" in url:
        return 401, {}, b""
    if any(path in url for path in ("/docs", "/redoc", "/openapi.json")):
        return 404, {}, b""
    return 200, {"Content-Type": "text/html"}, b'<div id="root"></div>'


def test_healthy_application_passes():
    with patch.object(module, "fetch", side_effect=healthy) as fetch:
        module.check("https://api.example.com", "https://dashboard.example.com")
        assert fetch.call_count == 9


@pytest.mark.parametrize(
    "failure", ["authorization", "docs", "frontend", "redirect", "health"]
)
def test_failed_contract_is_rejected(failure):
    def response(url):
        if failure == "authorization" and "users/me" in url:
            return 200, {}, b"{}"
        if failure == "docs" and url.endswith("/docs"):
            return 200, {}, b"docs"
        if failure == "frontend" and "dashboard" in url:
            return 200, {"Content-Type": "text/html"}, b"proxy error"
        if failure == "redirect" and url.startswith("http:"):
            return 200, {}, b""
        if failure == "health" and "health-check" in url:
            return 200, {}, b"false"
        return healthy(url)

    with patch.object(module, "fetch", side_effect=response), pytest.raises(ValueError):
        module.check("https://api.example.com", "https://dashboard.example.com")
