from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from scripts.quality.run_pytest_groups import (
    EXIT_TIMEOUT,
    PytestGroup,
    build_pytest_command,
    parse_group_spec,
    run_group,
    tail_lines,
)


def test_parse_group_spec_trims_name_and_targets() -> None:
    group = parse_group_spec(" api = tests/test_runtime_api.py , tests/test_rag_quality.py ")

    assert group == PytestGroup(
        "api",
        ("tests/test_runtime_api.py", "tests/test_rag_quality.py"),
    )


@pytest.mark.parametrize("spec", ["api", "=tests/test_runtime_api.py", "api="])
def test_parse_group_spec_rejects_invalid_specs(spec: str) -> None:
    with pytest.raises(ValueError):
        parse_group_spec(spec)


def test_build_pytest_command_appends_targets_before_pytest_args() -> None:
    command = build_pytest_command(
        PytestGroup("fast", ("tests/test_runtime_api.py",)),
        python_executable="python",
        pytest_args=("-q", "--maxfail=1"),
    )

    assert command == (
        "python",
        "-m",
        "pytest",
        "tests/test_runtime_api.py",
        "-q",
        "--maxfail=1",
    )


def test_tail_lines_reads_only_requested_suffix(tmp_path: Path) -> None:
    log_path = tmp_path / "pytest.log"
    log_path.write_text("one\ntwo\nthree\n", encoding="utf-8")

    assert tail_lines(log_path, 2) == ["two", "three"]
    assert tail_lines(log_path, 0) == []
    assert tail_lines(tmp_path / "missing.log", 2) == []


def test_run_group_success_writes_logs_and_command(tmp_path: Path) -> None:
    captured: dict[str, Any] = {}

    def popen_factory(command: tuple[str, ...], stdout: Any, stderr: Any) -> FinishedProcess:
        captured["command"] = command
        stdout.write(b"passed\n")
        stderr.write(b"")
        return FinishedProcess(exit_code=0)

    messages: list[str] = []
    result = run_group(
        PytestGroup("unit", ("tests/test_select_fast_tests.py",)),
        python_executable="python",
        pytest_args=("-q",),
        log_dir=tmp_path,
        timeout_seconds=None,
        idle_timeout_seconds=None,
        heartbeat_seconds=0,
        tail_lines_on_failure=2,
        popen_factory=popen_factory,
        emit=messages.append,
    )

    assert result.exit_code == 0
    assert captured["command"] == (
        "python",
        "-m",
        "pytest",
        "tests/test_select_fast_tests.py",
        "-q",
    )
    assert result.stdout_path.read_text(encoding="utf-8") == "passed\n"
    assert messages[-1] == "==> pytest group unit: passed"


def test_run_group_failure_prints_limited_log_tail(tmp_path: Path) -> None:
    def popen_factory(command: tuple[str, ...], stdout: Any, stderr: Any) -> FinishedProcess:
        stdout.write(b"line1\nline2\nline3\n")
        stderr.write(b"error1\nerror2\nerror3\n")
        return FinishedProcess(exit_code=2)

    messages: list[str] = []
    result = run_group(
        PytestGroup("api", ("tests/test_runtime_api.py",)),
        python_executable="python",
        pytest_args=("-q",),
        log_dir=tmp_path,
        timeout_seconds=None,
        idle_timeout_seconds=None,
        heartbeat_seconds=0,
        tail_lines_on_failure=2,
        popen_factory=popen_factory,
        emit=messages.append,
    )

    assert result.exit_code == 2
    assert "==> pytest group api stdout tail" in messages
    assert "line1" not in messages
    assert "line2" in messages
    assert "line3" in messages
    assert "==> pytest group api stderr tail" in messages
    assert "error1" not in messages
    assert "error2" in messages
    assert "error3" in messages


def test_run_group_idle_timeout_kills_process(tmp_path: Path) -> None:
    process = RunningProcess()

    def popen_factory(command: tuple[str, ...], stdout: Any, stderr: Any) -> RunningProcess:
        return process

    clock = FakeClock([0.0, 0.5, 1.0, 1.0])
    messages: list[str] = []
    result = run_group(
        PytestGroup("slow", ("tests/test_runtime_api.py",)),
        python_executable="python",
        pytest_args=("-q",),
        log_dir=tmp_path,
        timeout_seconds=None,
        idle_timeout_seconds=1.0,
        heartbeat_seconds=0,
        tail_lines_on_failure=2,
        popen_factory=popen_factory,
        now=clock,
        sleep=lambda _seconds: None,
        emit=messages.append,
    )

    assert result.exit_code == EXIT_TIMEOUT
    assert result.idle_timed_out is True
    assert process.killed is True
    assert messages[-1].startswith("==> pytest group slow: idle timed out")


class FinishedProcess:
    def __init__(self, *, exit_code: int) -> None:
        self.exit_code = exit_code

    def poll(self) -> int:
        return self.exit_code


class RunningProcess:
    def __init__(self) -> None:
        self.killed = False

    def poll(self) -> None:
        return None

    def kill(self) -> None:
        self.killed = True

    def wait(self, timeout: int | None = None) -> int:
        return EXIT_TIMEOUT


class FakeClock:
    def __init__(self, values: list[float]) -> None:
        self._values = values

    def __call__(self) -> float:
        if len(self._values) == 1:
            return self._values[0]
        return self._values.pop(0)
