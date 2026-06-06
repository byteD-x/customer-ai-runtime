from __future__ import annotations

import argparse
import json
import os
from collections.abc import Mapping
from typing import Any

import httpx

DEFAULT_TIMEOUT_SECONDS = 5.0


def run_checks(
    env: Mapping[str, str] | None = None,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    if env is None:
        env = os.environ
    checks = [
        _check_openai(env, timeout_seconds),
        _check_qdrant(env, timeout_seconds),
        _check_business_api(env, timeout_seconds),
        _check_ticket_api(env, timeout_seconds),
    ]
    status_counts: dict[str, int] = {}
    for check in checks:
        status = str(check["status"])
        status_counts[status] = status_counts.get(status, 0) + 1
    overall_status = "failed" if status_counts.get("failed") else "ready"
    if status_counts.get("passed", 0) == 0 and status_counts.get("failed", 0) == 0:
        overall_status = "skipped"
    return {
        "overall_status": overall_status,
        "status_counts": status_counts,
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check optional external integration readiness.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args()

    report = run_checks(timeout_seconds=args.timeout)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("external_readiness")
        for check in report["checks"]:
            print(f"- {check['name']}: {check['status']} ({check['message']})")
        print(f"overall_status: {report['overall_status']}")
    return 1 if report["overall_status"] == "failed" else 0


def _check_openai(env: Mapping[str, str], timeout_seconds: float) -> dict[str, Any]:
    api_key = env.get("CUSTOMER_AI_OPENAI_API_KEY")
    if not api_key:
        return _skipped("openai", "missing CUSTOMER_AI_OPENAI_API_KEY")
    base_url = (env.get("CUSTOMER_AI_OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    return _get_json(
        "openai",
        f"{base_url}/models",
        timeout_seconds=timeout_seconds,
        headers={"Authorization": "Bearer ***"},
        request_headers={"Authorization": f"Bearer {api_key}"},
    )


def _check_qdrant(env: Mapping[str, str], timeout_seconds: float) -> dict[str, Any]:
    url = env.get("CUSTOMER_AI_QDRANT_URL")
    if not url:
        return _skipped("qdrant", "missing CUSTOMER_AI_QDRANT_URL")
    api_key = env.get("CUSTOMER_AI_QDRANT_API_KEY")
    request_headers = {"api-key": api_key} if api_key else {}
    safe_headers = {"api-key": "***"} if api_key else {}
    return _get_json(
        "qdrant",
        f"{url.rstrip('/')}/collections",
        timeout_seconds=timeout_seconds,
        headers=safe_headers,
        request_headers=request_headers,
    )


def _check_business_api(env: Mapping[str, str], timeout_seconds: float) -> dict[str, Any]:
    base_url = env.get("CUSTOMER_AI_BUSINESS_API_BASE_URL")
    if not base_url:
        return _skipped("business_api", "missing CUSTOMER_AI_BUSINESS_API_BASE_URL")
    api_key = env.get("CUSTOMER_AI_BUSINESS_API_KEY")
    request_headers = {"X-Business-API-Key": api_key} if api_key else {}
    safe_headers = {"X-Business-API-Key": "***"} if api_key else {}
    return _get_json(
        "business_api",
        f"{base_url.rstrip('/')}/healthz",
        timeout_seconds=timeout_seconds,
        headers=safe_headers,
        request_headers=request_headers,
    )


def _check_ticket_api(env: Mapping[str, str], timeout_seconds: float) -> dict[str, Any]:
    base_url = env.get("CUSTOMER_AI_TICKET_API_BASE_URL")
    if not base_url:
        return _skipped("ticket_api", "missing CUSTOMER_AI_TICKET_API_BASE_URL")
    api_key = env.get("CUSTOMER_AI_TICKET_API_KEY")
    request_headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    safe_headers = {"Authorization": "Bearer ***"} if api_key else {}
    return _get_json(
        "ticket_api",
        f"{base_url.rstrip('/')}/healthz",
        timeout_seconds=timeout_seconds,
        headers=safe_headers,
        request_headers=request_headers,
    )


def _get_json(
    name: str,
    url: str,
    *,
    timeout_seconds: float,
    headers: dict[str, str],
    request_headers: dict[str, str],
) -> dict[str, Any]:
    try:
        response = httpx.get(url, headers=request_headers, timeout=timeout_seconds)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        return {
            "name": name,
            "status": "failed",
            "message": exc.__class__.__name__,
            "url": url,
            "headers": headers,
        }
    return {
        "name": name,
        "status": "passed",
        "message": f"HTTP {response.status_code}",
        "url": url,
        "headers": headers,
    }


def _skipped(name: str, message: str) -> dict[str, Any]:
    return {
        "name": name,
        "status": "skipped",
        "message": message,
    }


if __name__ == "__main__":
    raise SystemExit(main())
