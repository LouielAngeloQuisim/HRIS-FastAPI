"""Read-only smoke probes; no credentials or response bodies logged."""
import argparse
import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def fetch(url):
    try:
        with build_opener(NoRedirect).open(Request(url), timeout=15) as response:
            return response.status, response.headers, response.read(1024 * 1024)
    except HTTPError as error:
        return error.code, error.headers, error.read(1024 * 1024)

def check(api, frontend):
    probes = [("health", api + "/api/v1/utils/health-check/", 200),
              ("anonymous-user", api + "/api/v1/users/me", 401),
              ("docs", api + "/docs", 404), ("redoc", api + "/redoc", 404),
              ("openapi", api + "/api/v1/openapi.json", 404),
              ("frontend", frontend + "/", 200),
              ("frontend-sign-in", frontend + "/sign-in", 200)]
    for label, url, expected in probes:
        status, headers, body = fetch(url)
        if status != expected:
            raise ValueError(f"{label}: HTTP {status}, expected {expected}")
        if label == "health" and json.loads(body) is not True:
            raise ValueError("health: unexpected JSON")
        if label.startswith("frontend"):
            if "text/html" not in headers.get("Content-Type", "") or b'id="root"' not in body:
                raise ValueError(f"{label}: missing application shell")
        print(f"{label}: HTTP {status}")
    for base in (api, frontend):
        parts = urlsplit(base)
        status, headers, _ = fetch("http://" + parts.netloc + "/")
        if status not in (301, 302, 307, 308) or headers.get("Location") != base + "/":
            raise ValueError("HTTP to HTTPS redirect failed")
        print(f"HTTPS redirect: HTTP {status}")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="https://api.hrisly.duckdns.org")
    parser.add_argument("--frontend", default="https://dashboard.hrisly.duckdns.org")
    parser.add_argument("--attempts", type=int, default=12)
    args = parser.parse_args()
    for base in (args.api, args.frontend):
        if urlsplit(base).scheme != "https" or urlsplit(base).path not in ("", "/"):
            parser.error("base URLs must use HTTPS with no path")
    for attempt in range(args.attempts):
        try:
            check(args.api.rstrip("/"), args.frontend.rstrip("/"))
            return 0
        except (ValueError, URLError, TimeoutError) as error:
            print(f"Attempt {attempt + 1} failed: {type(error).__name__}")
            if attempt + 1 < args.attempts:
                time.sleep(10)
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
