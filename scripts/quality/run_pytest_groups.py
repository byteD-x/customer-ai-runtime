from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

EXIT_TIMEOUT = 124


@dataclass(frozen=True)
class PytestGroup:
    name: str
    targets: tuple[str, ...]


@dataclass(frozen=True)
class GroupRunResult:
    name: str
    command: tuple[str, ...]
    exit_code: int
    duration_seconds: float
    stdout_path: Path
    stderr_path: Path
    timed_out: bool = False
    idle_timed_out: bool = False


def parse_group_spec(spec: str) -> PytestGroup:
    name, separator, raw_targets = spec.partition("=")
    group_name = name.strip()
    if not separator or not group_name:
        raise ValueError("group must use NAME=target[,target...] format")
    targets = tuple(target.strip() for target in raw_targets.split(",") if target.strip())
    if not targets:
        raise ValueError(f"group {group_name!r} must include at least one pytest target")
    return PytestGroup(group_name, targets)


def build_pytest_command(
    group: PytestGroup,
    *,
    python_executable: str,
    pytest_args: Sequence[str],
) -> tuple[str, ...]:
    return (python_executable, "-m", "pytest", *group.targets, *pytest_args)


def tail_lines(path: Path, line_count: int) -> list[str]:
    if line_count <= 0 or not path.exists():
        return []
    return path.read_text(encoding="utf-8", errors="replace").splitlines()[-line_count:]


def run_group(
    group: PytestGroup,
    *,
    python_executable: str,
    pytest_args: Sequence[str],
    log_dir: Path,
    timeout_seconds: float | None,
    idle_timeout_seconds: float | None,
    heartbeat_seconds: float,
    tail_lines_on_failure: int,
    popen_factory: Callable[..., Any] = subprocess.Popen,
    now: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    emit: Callable[[str], None] = print,
) -> GroupRunResult:
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / f"{group.name}.stdout.log"
    stderr_path = log_dir / f"{group.name}.stderr.log"
    command = build_pytest_command(
        group,
        python_executable=python_executable,
        pytest_args=pytest_args,
    )

    start = now()
    emit(f"==> pytest group {group.name}: {' '.join(command)}")
    with stdout_path.open("wb") as stdout_file, stderr_path.open("wb") as stderr_file:
        process = popen_factory(command, stdout=stdout_file, stderr=stderr_file)
        last_log_size = _combined_log_size(stdout_path, stderr_path)
        last_activity = start
        next_heartbeat = start + heartbeat_seconds
        timed_out = False
        idle_timed_out = False

        while True:
            exit_code = process.poll()
            current = now()
            current_log_size = _combined_log_size(stdout_path, stderr_path)
            if current_log_size != last_log_size:
                last_log_size = current_log_size
                last_activity = current

            if exit_code is not None:
                break
            if timeout_seconds is not None and current - start >= timeout_seconds:
                timed_out = True
                exit_code = EXIT_TIMEOUT
                _kill_process(process)
                break
            if idle_timeout_seconds is not None and current - last_activity >= idle_timeout_seconds:
                idle_timed_out = True
                exit_code = EXIT_TIMEOUT
                _kill_process(process)
                break
            if heartbeat_seconds > 0 and current >= next_heartbeat:
                emit(
                    "==> pytest group "
                    f"{group.name}: running {current - start:.1f}s, "
                    f"stdout={stdout_path.stat().st_size if stdout_path.exists() else 0}B, "
                    f"stderr={stderr_path.stat().st_size if stderr_path.exists() else 0}B, "
                    f"idle={current - last_activity:.1f}s"
                )
                next_heartbeat = current + heartbeat_seconds
            sleep(0.2)

    duration = now() - start
    result = GroupRunResult(
        name=group.name,
        command=command,
        exit_code=int(exit_code),
        duration_seconds=duration,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        timed_out=timed_out,
        idle_timed_out=idle_timed_out,
    )
    _emit_result(result, tail_lines_on_failure=tail_lines_on_failure, emit=emit)
    return result


def run_groups(
    groups: Iterable[PytestGroup],
    *,
    python_executable: str,
    pytest_args: Sequence[str],
    log_dir: Path,
    timeout_seconds: float | None,
    idle_timeout_seconds: float | None,
    heartbeat_seconds: float,
    tail_lines_on_failure: int,
    emit: Callable[[str], None] = print,
) -> list[GroupRunResult]:
    results: list[GroupRunResult] = []
    for group in groups:
        result = run_group(
            group,
            python_executable=python_executable,
            pytest_args=pytest_args,
            log_dir=log_dir,
            timeout_seconds=timeout_seconds,
            idle_timeout_seconds=idle_timeout_seconds,
            heartbeat_seconds=heartbeat_seconds,
            tail_lines_on_failure=tail_lines_on_failure,
            emit=emit,
        )
        results.append(result)
        if result.exit_code != 0:
            break
    return results


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run pytest targets in named groups.")
    parser.add_argument(
        "--group",
        action="append",
        default=[],
        help="Pytest group in NAME=target[,target...] format. Can be passed multiple times.",
    )
    parser.add_argument("--python", default=sys.executable, help="Python executable.")
    parser.add_argument(
        "--pytest-arg",
        action="append",
        default=["-q"],
        help="Extra pytest argument. Defaults to -q; pass multiple times for more args.",
    )
    parser.add_argument("--log-dir", default=None, help="Directory for stdout/stderr logs.")
    parser.add_argument("--timeout-seconds", type=float, default=None)
    parser.add_argument("--idle-timeout-seconds", type=float, default=None)
    parser.add_argument("--heartbeat-seconds", type=float, default=10.0)
    parser.add_argument("--tail-lines-on-failure", type=int, default=40)
    args = parser.parse_args(argv)

    if not args.group:
        parser.error("at least one --group is required")
    try:
        groups = [parse_group_spec(spec) for spec in args.group]
    except ValueError as error:
        parser.error(str(error))

    log_dir = (
        Path(args.log_dir)
        if args.log_dir
        else Path(tempfile.mkdtemp(prefix="customer_ai_runtime_pytest_groups_"))
    )
    print(f"==> pytest group logs: {log_dir}")
    results = run_groups(
        groups,
        python_executable=args.python,
        pytest_args=tuple(args.pytest_arg),
        log_dir=log_dir,
        timeout_seconds=args.timeout_seconds,
        idle_timeout_seconds=args.idle_timeout_seconds,
        heartbeat_seconds=args.heartbeat_seconds,
        tail_lines_on_failure=args.tail_lines_on_failure,
    )
    failed = next((result for result in results if result.exit_code != 0), None)
    return 0 if failed is None else failed.exit_code


def _combined_log_size(*paths: Path) -> int:
    return sum(path.stat().st_size for path in paths if path.exists())


def _kill_process(process: Any) -> None:
    process.kill()
    try:
        process.wait(timeout=5)
    except TypeError:
        process.wait()
    except subprocess.TimeoutExpired:
        pass


def _emit_result(
    result: GroupRunResult,
    *,
    tail_lines_on_failure: int,
    emit: Callable[[str], None],
) -> None:
    status = "passed" if result.exit_code == 0 else f"failed exit={result.exit_code}"
    if result.timed_out:
        status = f"timed out after {result.duration_seconds:.1f}s"
    if result.idle_timed_out:
        status = f"idle timed out after {result.duration_seconds:.1f}s"
    emit(f"==> pytest group {result.name}: {status}")
    if result.exit_code == 0:
        return
    for label, path in (("stdout", result.stdout_path), ("stderr", result.stderr_path)):
        lines = tail_lines(path, tail_lines_on_failure)
        if not lines:
            continue
        emit(f"==> pytest group {result.name} {label} tail")
        for line in lines:
            emit(line)


if __name__ == "__main__":
    raise SystemExit(main())
