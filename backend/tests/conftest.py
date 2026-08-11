from __future__ import annotations

from collections import defaultdict
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete

from app.auth.models import RefreshToken
from app.config.database import engine, init_db
from app.config.settings import settings
from app.item.models import Item
from app.main import app
from app.user.models import User
from tests.utils.user import authentication_token_from_email
from tests.utils.utils import get_superuser_token_headers

# Phase 1 tables, ordered so FK-referencing tables are deleted first.
PHASE1_TABLES = [
    "emp_task",
    "employee_projects",
    "category",
    "lots",
    "blocks",
    "phase",
    "model",
    "model_types",
    "owner",
    "project",
    "project_type",
    "position",
    "employee_attachments",
    "employee_additional_records",
    "employee_records",
    "subdivision",
    "department",
    "division",
]


@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        init_db(session)
        yield session
        session.execute(delete(RefreshToken))
        statement = delete(Item)
        session.execute(statement)
        from sqlmodel import text as _text

        for table in PHASE1_TABLES:
            session.exec(_text(f"DELETE FROM {table}"))
        session.execute(delete(User))
        session.commit()


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def superuser_token_headers(client: TestClient) -> dict[str, str]:
    return get_superuser_token_headers(client)


@pytest.fixture(scope="module")
def normal_user_token_headers(client: TestClient, db: Session) -> dict[str, str]:
    return authentication_token_from_email(
        client=client, email=settings.EMAIL_TEST_USER, db=db
    )


def pytest_terminal_summary(
    terminalreporter: pytest.TerminalReporter,
    exitstatus: int,
    config: pytest.Config,
) -> None:
    """Print a per-module pass/fail summary after the default reporter.

    Groups results by the first sub-directory of each test's nodeid
    (e.g. ``tests/auth/test_x.py`` -> ``auth``). Does not change the exit
    code, so the CI coverage gate is unaffected.
    """
    counts: dict[str, dict[str, int]] = defaultdict(
        lambda: {"passed": 0, "failed": 0, "error": 0, "skipped": 0}
    )
    category_map = {
        "passed": "passed",
        "failed": "failed",
        "error": "error",
        "skipped": "skipped",
    }
    for category, reports in terminalreporter.stats.items():
        key = category_map.get(category)
        if not key:
            continue
        for report in reports:
            nodeid = getattr(report, "nodeid", "") or ""
            module = nodeid.split("/", 2)[1] if "/" in nodeid else nodeid or "misc"
            counts[module][key] += 1

    if not counts:
        return

    terminalreporter.write_sep("=", "Module summary")
    total = {"passed": 0, "failed": 0, "error": 0, "skipped": 0}
    for module in sorted(counts):
        g = counts[module]
        if g["failed"] or g["error"]:
            status, markup = "FAILED", {"red": True, "bold": True}
        elif g["passed"]:
            status, markup = "PASSED", {"green": True}
        else:
            status, markup = "SKIPPED", {"yellow": True}
        line = (
            f"  {module:12} {status:7}  "
            f"(passed={g['passed']}, failed={g['failed']}, "
            f"error={g['error']}, skipped={g['skipped']})"
        )
        terminalreporter.write_line(line, **markup)
        for k in total:
            total[k] += g[k]

    summary = (
        f"  TOTAL         "
        f"(passed={total['passed']}, failed={total['failed']}, "
        f"error={total['error']}, skipped={total['skipped']})"
    )
    terminalreporter.write_line("")
    terminalreporter.write_line(summary, bold=True)
