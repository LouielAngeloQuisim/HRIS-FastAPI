"""The QA entry point refuses remote targets and unsafe filters before tools run."""

import os
import subprocess
from pathlib import Path

import pytest

RUNNER = Path(__file__).resolve().parents[2] / "scripts" / "run-e2e-qa.sh"


@pytest.mark.parametrize("key", ["E2E_BASE_URL", "E2E_API_URL"])
@pytest.mark.parametrize(
    "url", ["https://production.invalid", "http://127.0.0.1:8000@production.invalid"]
)
def test_qa_runner_rejects_remote_urls_before_starting_services(
    key: str, url: str
) -> None:
    result = subprocess.run(
        ["bash", str(RUNNER)],
        env={**os.environ, key: url},
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode != 0
    assert "Refusing non-loopback" in result.stderr


@pytest.mark.parametrize(
    "filter_path", ["../outside", "--config=remote.ts", "nonexistent.spec.ts"]
)
def test_qa_runner_rejects_unsafe_spec_filters(filter_path: str) -> None:
    environment = {
        **os.environ,
        "E2E_BASE_URL": "http://127.0.0.1:5173",
        "E2E_API_URL": "http://127.0.0.1:8000/api/v1",
    }
    result = subprocess.run(
        ["bash", str(RUNNER), filter_path],
        env=environment,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 2
    assert "existing path relative" in result.stderr


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("E2E_WORKERS", "0", "E2E_WORKERS must be an integer from 1 to 4"),
        ("E2E_WORKERS", "five", "E2E_WORKERS must be an integer from 1 to 4"),
        (
            "E2E_COMMAND_TIMEOUT_SECONDS",
            "0",
            "E2E_COMMAND_TIMEOUT_SECONDS must be an integer from 1 to 900",
        ),
        (
            "E2E_SUITE_TIMEOUT_SECONDS",
            "99999",
            "E2E_SUITE_TIMEOUT_SECONDS must be an integer from 1 to 2400",
        ),
    ],
)
def test_qa_runner_rejects_unbounded_or_invalid_execution_settings(
    key: str, value: str, message: str
) -> None:
    environment = {
        **os.environ,
        "E2E_BASE_URL": "http://127.0.0.1:5173",
        "E2E_API_URL": "http://127.0.0.1:8000/api/v1",
        key: value,
    }
    result = subprocess.run(
        ["bash", str(RUNNER)],
        env=environment,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 2
    assert message in result.stderr
