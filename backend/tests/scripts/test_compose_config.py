"""Validate deployment Compose without reading .env or resolving credentials."""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]

@pytest.mark.parametrize("filename", ["compose.prod.yml", "compose.traefik.yml"])
def test_deployment_compose_is_valid_without_secrets(filename):
    if not shutil.which("docker"):
        pytest.skip("Docker Compose CLI unavailable")
    result = subprocess.run(
        ["docker", "compose", "--env-file", "/dev/null", "-f", str(ROOT / filename),
         "config", "--no-env-resolution", "--no-interpolate", "--quiet"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
