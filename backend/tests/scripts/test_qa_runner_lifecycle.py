"""Fault-inject local E2E startup and interruption to verify owned cleanup."""

import os
import signal
import subprocess
import time
from pathlib import Path

RUNNER = Path(__file__).resolve().parents[3] / "scripts" / "run-e2e-qa.sh"


def _fake_tools(tmp_path: Path) -> tuple[dict[str, str], Path]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    events = tmp_path / "docker-events.log"
    docker = fake_bin / "docker"
    docker.write_text(
        """#!/usr/bin/env python3
import os, sys
args = sys.argv[1:]
with open(os.environ['QA_DOCKER_EVENTS'], 'a', encoding='utf-8') as output:
    output.write(' '.join(args) + '\\n')
joined = ' '.join(args)
if args[:2] == ['inspect', 'hris-ui-qa-e2e']:
    if '--format' not in args:
        raise SystemExit(0)
    template = args[args.index('--format') + 1]
    if '.Config.Image' in template: print('postgres:18')
    elif '.State.Running' in template: print(os.environ.get('QA_CONTAINER_RUNNING', 'false'))
    elif '.Config.Env' in template: print('POSTGRES_USER=e2e\\nPOSTGRES_DB=e2e\\nPOSTGRES_PASSWORD=e2e-placeholder')
    raise SystemExit(0)
if args[:2] == ['exec', 'hris-ui-qa-e2e'] and 'pg_isready' in joined:
    raise SystemExit(0)
if args[:2] == ['exec', 'hris-ui-qa-e2e'] and 'psql' in joined:
    if 'DROP DATABASE' in joined and os.environ.get('QA_DOCKER_FAIL_DROP') == 'true':
        raise SystemExit(2)
    raise SystemExit(0)
if args[:2] in (['start', 'hris-ui-qa-e2e'], ['stop', 'hris-ui-qa-e2e']):
    raise SystemExit(0)
raise SystemExit('unexpected docker command: ' + joined)
"""
    )
    docker.chmod(0o755)
    uv = fake_bin / "uv"
    uv.write_text(
        """#!/usr/bin/env python3
import os, sys, time, subprocess, signal
if not any(argument.endswith('prestart.sh') for argument in sys.argv):
    raise SystemExit('unexpected uv command')
mode = os.environ['QA_UV_MODE']
if mode == 'fail':
    print('injected prestart failure', file=sys.stderr)
    raise SystemExit(23)
if mode == 'descendants':
    child = subprocess.Popen([sys.executable, '-c', 'import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)'])
    open(os.environ['QA_CHILD_PID'], 'w').write(str(child.pid))
open(os.environ['QA_UV_STARTED'], 'w').write(str(os.getpid()))
while True: time.sleep(0.2)
"""
    )
    uv.chmod(0o755)
    pnpm = fake_bin / "pnpm"
    pnpm.write_text("#!/bin/sh\nprintf 'pnpm\\n' >>\"$QA_PNPM_CALLED\"\nexit 99\n")
    pnpm.chmod(0o755)
    environment = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "QA_DOCKER_EVENTS": str(events),
        "QA_PNPM_CALLED": str(tmp_path / "pnpm-called"),
        "QA_UV_STARTED": str(tmp_path / "uv-started"),
        "E2E_COMMAND_TIMEOUT_SECONDS": "30",
    }
    return environment, events


def _wait_for(path: Path, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if path.exists():
            return
        if process.poll() is not None:
            raise AssertionError(
                f"runner exited early with status {process.returncode}"
            )
        time.sleep(0.05)
    raise AssertionError("injected startup command did not begin")


def _process_is_running(pid: int) -> bool:
    try:
        state = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").split()[2]
    except FileNotFoundError:
        return False
    return state != "Z"


def _assert_owned_resources_cleaned(events: Path) -> None:
    commands = events.read_text(encoding="utf-8").splitlines()
    create = next(
        command for command in commands if "CREATE DATABASE hris_qa_" in command
    )
    drop = next(
        command for command in commands if "DROP DATABASE IF EXISTS hris_qa_" in command
    )
    created_db = create.split("CREATE DATABASE ", 1)[1].split()[0]
    dropped_db = drop.split("DROP DATABASE IF EXISTS ", 1)[1].split()[0]
    assert created_db == dropped_db
    assert created_db.startswith("hris_qa_")
    assert "stop hris-ui-qa-e2e" in commands
    assert not any(command.startswith("rm ") for command in commands)


def test_qa_runner_cleans_only_its_database_and_restores_stopped_container_after_setup_failure(
    tmp_path: Path,
) -> None:
    environment, events = _fake_tools(tmp_path)
    environment["QA_UV_MODE"] = "fail"
    result = subprocess.run(
        ["bash", str(RUNNER)],
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert result.returncode == 23, result.stderr
    assert "injected prestart failure" in result.stderr
    assert not Path(environment["QA_PNPM_CALLED"]).exists()
    _assert_owned_resources_cleaned(events)


def test_qa_runner_reports_cleanup_failure_without_losing_setup_failure(
    tmp_path: Path,
) -> None:
    environment, events = _fake_tools(tmp_path)
    environment["QA_UV_MODE"] = "fail"
    environment["QA_DOCKER_FAIL_DROP"] = "true"
    result = subprocess.run(
        ["bash", str(RUNNER)],
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert result.returncode == 23, result.stderr
    assert "QA cleanup failed: could not drop this run's database" in result.stderr
    assert "stop hris-ui-qa-e2e" in events.read_text(encoding="utf-8")


def test_qa_runner_leaves_preexisting_running_container_running_after_setup_failure(
    tmp_path: Path,
) -> None:
    environment, events = _fake_tools(tmp_path)
    environment["QA_UV_MODE"] = "fail"
    environment["QA_CONTAINER_RUNNING"] = "true"
    result = subprocess.run(
        ["bash", str(RUNNER)],
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert result.returncode == 23, result.stderr
    commands = events.read_text(encoding="utf-8").splitlines()
    assert not any(command.startswith("stop ") for command in commands)
    assert not any(command.startswith("rm ") for command in commands)


def test_qa_runner_cleans_only_its_database_and_restores_stopped_container_on_sigterm(
    tmp_path: Path,
) -> None:
    environment, events = _fake_tools(tmp_path)
    environment["QA_UV_MODE"] = "block"
    started = Path(environment["QA_UV_STARTED"])
    process = subprocess.Popen(
        ["bash", str(RUNNER)],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        _wait_for(started, process)
        uv_pid = int(started.read_text(encoding="utf-8"))
        os.kill(process.pid, signal.SIGTERM)
        _stdout, stderr = process.communicate(timeout=15)
    finally:
        if process.poll() is None:
            os.kill(process.pid, signal.SIGKILL)
            process.communicate(timeout=5)

    assert process.returncode == 143, stderr
    deadline = time.monotonic() + 3
    while _process_is_running(uv_pid) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not _process_is_running(uv_pid), (
        "startup process survived runner interruption"
    )
    _assert_owned_resources_cleaned(events)


def test_qa_runner_timeout_kills_term_resistant_descendant(tmp_path: Path) -> None:
    environment, events = _fake_tools(tmp_path)
    environment.update(
        QA_UV_MODE="descendants",
        E2E_COMMAND_TIMEOUT_SECONDS="1",
        QA_CHILD_PID=str(tmp_path / "child-pid"),
    )
    process = subprocess.Popen(
        ["bash", str(RUNNER)],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    child_pid = None
    try:
        _wait_for(Path(environment["QA_UV_STARTED"]), process)
        child_pid = int(Path(environment["QA_CHILD_PID"]).read_text())
        _, stderr = process.communicate(timeout=15)
        assert process.returncode == 124, stderr
        assert not _process_is_running(child_pid), "descendant survived timeout"
        _assert_owned_resources_cleaned(events)
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=5)
        if child_pid and _process_is_running(child_pid):
            os.kill(child_pid, signal.SIGKILL)
