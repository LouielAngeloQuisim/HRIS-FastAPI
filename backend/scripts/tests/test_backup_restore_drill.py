"""Phase B7 — automated test for the backup/restore drill script.

The drill dumps the live database, restores it into a throwaway database, and
validates the result. A full drill requires ``pg_dump``/``psql`` and a live DB,
so the functional run is gated behind ``RUN_BACKUP_DRILL=1``; the structural
tests always run and catch a broken/renamed script in CI.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "backup-restore-drill.sh"


def test_script_exists_and_is_executable() -> None:
    assert SCRIPT.exists(), f"drill script missing at {SCRIPT}"
    assert os.access(SCRIPT, os.X_OK), "drill script is not executable"


def test_script_has_valid_bash_syntax() -> None:
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_script_contains_required_drill_steps() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    for required in (
        "set -euo pipefail",
        "pg_dump",
        'CREATE DATABASE',
        "DRILL_DB",
        "DROP DATABASE",
        "exit 1",
    ):
        assert required in text, f"drill script is missing required step: {required!r}"


@pytest.mark.skipif(
    os.environ.get("RUN_BACKUP_DRILL") != "1",
    reason="set RUN_BACKUP_DRILL=1 (and provide a live DB + pg tools) to run the drill",
)
def test_full_drill_passes_against_live_db() -> None:
    env = {**os.environ}
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert result.returncode == 0, f"drill failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    assert "DRILL PASSED" in result.stdout
