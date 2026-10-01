"""#83 - API docs are served only in local environments.

Covers the pure docs_urls() helper wired into the FastAPI constructor in
app/main.py: /docs, /redoc and openapi.json must be disabled (None) outside
local so the production API surface is not published, and must stay on for
local and CI.
"""

from app.main import docs_urls


class TestDocsUrls:
    def test_non_local_environments_disable_all_doc_urls(self) -> None:
        for environment in ("staging", "production"):
            urls = docs_urls(environment)
            assert urls["openapi_url"] is None, environment
            assert urls["docs_url"] is None, environment
            assert urls["redoc_url"] is None, environment

    def test_local_environment_keeps_doc_urls_enabled(self) -> None:
        urls = docs_urls("local")
        assert urls["openapi_url"] is not None
        assert urls["docs_url"] is not None
        assert urls["redoc_url"] is not None
        assert str(urls["openapi_url"]).endswith("/openapi.json")
