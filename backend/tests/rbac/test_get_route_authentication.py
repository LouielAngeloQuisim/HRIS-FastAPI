"""Exercise every production GET API route without usable credentials."""
import re

import pytest
from fastapi.routing import APIRoute

from app.common.route_policy import is_local_only, is_public
from app.main import app

PROTECTED_GETS = sorted({
    route.path
    for route in app.routes
    if isinstance(route, APIRoute)
    and "GET" in route.methods
    and not is_public("GET", route.path)
    and not is_local_only(route.path)
})
PUBLIC_GETS = sorted({
    route.path
    for route in app.routes
    if isinstance(route, APIRoute)
    and "GET" in route.methods
    and is_public("GET", route.path)
})


@pytest.mark.parametrize("path", PROTECTED_GETS)
@pytest.mark.parametrize("authorization", [None, "Bearer invalid-test-token"])
def test_get_route_rejects_unusable_credentials(client, path, authorization):
    resolved = re.sub(
        r"\{[^}]+\}", "00000000-0000-0000-0000-000000000000", path
    )
    headers = {"Authorization": authorization} if authorization else {}
    response = client.get(resolved, headers=headers, follow_redirects=False)
    assert response.status_code == 401, f"{path}: {response.status_code}"
    assert response.json()["success"] is False


@pytest.mark.parametrize("path", PUBLIC_GETS)
def test_explicit_public_get_is_reachable_without_credentials(client, path):
    response = client.get(path, follow_redirects=False)
    assert response.status_code == 200
    assert response.json() is True


def test_get_inventory_is_not_empty():
    assert PROTECTED_GETS
    assert PUBLIC_GETS == ["/api/v1/utils/health-check/"]
