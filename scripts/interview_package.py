# ruff: noqa: E402, I001
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from examples.interview_demo import (
    render_markdown_report,
    run_demo,
    write_output_file,
)
from scripts.check_external_readiness import (
    _render_output as render_readiness_output,
    run_checks,
    write_output_file as write_readiness_output_file,
)
from scripts.eval_online_rag import (
    _render_output as render_online_eval_output,
    run_online_eval,
    write_output_file as write_online_eval_output_file,
)
from scripts.eval_rag import (
    _render_output as render_rag_eval_output,
    run_eval,
    write_output_file as write_rag_eval_output_file,
)

DEFAULT_OUTPUT_DIR = Path(".codex")
DEFAULT_READINESS_TIMEOUT_SECONDS = 5.0


def run_package(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    online_rag_sample_path: Path | None = None,
    readiness_timeout_seconds: float = DEFAULT_READINESS_TIMEOUT_SECONDS,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    output_dir = _resolve_output_dir(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    interview_result = run_demo()
    rag_report = run_eval()
    readiness_report = run_checks(env=env, timeout_seconds=readiness_timeout_seconds)

    interview_report_path = output_dir / "interview-demo-report.md"
    rag_eval_report_path = output_dir / "rag-eval-report.json"
    readiness_report_path = output_dir / "external-readiness-report.json"

    write_output_file(interview_report_path, render_markdown_report(interview_result))
    write_rag_eval_output_file(
        rag_eval_report_path,
        render_rag_eval_output(rag_report, json_output=True),
    )
    write_readiness_output_file(
        readiness_report_path,
        render_readiness_output(readiness_report, json_output=True),
    )

    generated: dict[str, str] = {
        "interview_demo_report": str(interview_report_path),
        "rag_eval_report": str(rag_eval_report_path),
        "external_readiness_report": str(readiness_report_path),
    }

    online_eval_report: dict[str, Any] | None = None
    if online_rag_sample_path is not None:
        online_eval_report = run_online_eval(online_rag_sample_path)
        online_eval_report_path = output_dir / "online-rag-eval-report.json"
        write_online_eval_output_file(
            online_eval_report_path,
            render_online_eval_output(online_eval_report, json_output=True),
        )
        generated["online_rag_eval_report"] = str(online_eval_report_path)

    return {
        "generated": generated,
        "interview_demo": interview_result,
        "rag_eval": rag_report,
        "external_readiness": readiness_report,
        "online_rag_eval": online_eval_report,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the interview material package.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for generated reports.",
    )
    parser.add_argument(
        "--online-rag-sample-path",
        type=Path,
        default=None,
        help="Optional anonymized online RAG sample input.",
    )
    parser.add_argument(
        "--readiness-timeout",
        type=float,
        default=DEFAULT_READINESS_TIMEOUT_SECONDS,
        help="Timeout in seconds for external readiness checks.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    result = run_package(
        output_dir=args.output_dir,
        online_rag_sample_path=args.online_rag_sample_path,
        readiness_timeout_seconds=args.readiness_timeout,
    )
    output_text = _render_output(result, json_output=args.json)
    print(output_text, end="")

    interview_failed = int(result["interview_demo"]["rag_eval_summary"]["failed"])
    rag_failed = int(result["rag_eval"]["summary"]["failed"])
    readiness_failed = result["external_readiness"]["overall_status"] == "failed"
    online_failed = bool(
        result["online_rag_eval"] and result["online_rag_eval"]["summary"]["failed"]
    )
    return 1 if (interview_failed or rag_failed or readiness_failed or online_failed) else 0


def _render_output(result: dict[str, Any], *, json_output: bool) -> str:
    if json_output:
        return json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    lines = ["interview_package"]
    for key, path in result["generated"].items():
        lines.append(f"- {key}: {path}")
    return "\n".join(lines) + "\n"


def _resolve_output_dir(output_dir: Path) -> Path:
    if output_dir.is_absolute():
        return output_dir
    return REPO_ROOT / output_dir


if __name__ == "__main__":
    raise SystemExit(main())
