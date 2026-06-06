from __future__ import annotations

import argparse
import json
import os
import socket
from collections.abc import Callable, Mapping
from typing import Any

import httpx

DEFAULT_TIMEOUT_SECONDS = 5.0
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_OPENAI_ADMIN_BASE_URL = "https://api.openai.com/v1"
DEFAULT_OPENAI_ADMIN_USAGE_PATH = "/organization/usage/completions?limit=1"
DEFAULT_OPENAI_ADMIN_COSTS_PATH = "/organization/costs?limit=1"

HttpGet = Callable[[str, dict[str, str], float], int]
TcpConnect = Callable[[str, int, float], None]


def run_checks(
    env: Mapping[str, str] | None = None,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    http_get: HttpGet | None = None,
    tcp_connect: TcpConnect | None = None,
) -> dict[str, Any]:
    if env is None:
        env = os.environ
    http_get = http_get or _http_get
    tcp_connect = tcp_connect or _tcp_connect
    checks = [
        _check_openai_models(env, timeout_seconds, http_get),
        _check_openai_admin_usage(env, timeout_seconds, http_get),
        _check_openai_admin_costs(env, timeout_seconds, http_get),
        _check_qdrant_health(env, timeout_seconds, http_get),
        _check_qdrant_collections(env, timeout_seconds, http_get),
        _check_business_api(env, timeout_seconds, http_get),
        _check_ticket_api(env, timeout_seconds, http_get),
        _check_redis_queue(env, timeout_seconds, tcp_connect),
        _check_postgres_queue(env, timeout_seconds, tcp_connect),
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


def _check_openai_models(
    env: Mapping[str, str],
    timeout_seconds: float,
    http_get: HttpGet,
) -> dict[str, Any]:
    api_key = env.get("CUSTOMER_AI_OPENAI_API_KEY")
    if not api_key:
        return _skipped("openai_models", "missing CUSTOMER_AI_OPENAI_API_KEY")
    base_url = (env.get("CUSTOMER_AI_OPENAI_BASE_URL") or DEFAULT_OPENAI_BASE_URL).rstrip("/")
    return _get_json(
        "openai_models",
        f"{base_url}/models",
        timeout_seconds=timeout_seconds,
        headers={"Authorization": "Bearer ***"},
        request_headers={"Authorization": f"Bearer {api_key}"},
        http_get=http_get,
    )


def _check_openai_admin_usage(
    env: Mapping[str, str],
    timeout_seconds: float,
    http_get: HttpGet,
) -> dict[str, Any]:
    return _check_openai_admin_endpoint(
        env,
        timeout_seconds,
        http_get,
        name="openai_admin_usage",
        path_env="CUSTOMER_AI_OPENAI_ADMIN_USAGE_PATH",
        default_path=DEFAULT_OPENAI_ADMIN_USAGE_PATH,
    )


def _check_openai_admin_costs(
    env: Mapping[str, str],
    timeout_seconds: float,
    http_get: HttpGet,
) -> dict[str, Any]:
    return _check_openai_admin_endpoint(
        env,
        timeout_seconds,
        http_get,
        name="openai_admin_costs",
        path_env="CUSTOMER_AI_OPENAI_ADMIN_COSTS_PATH",
        default_path=DEFAULT_OPENAI_ADMIN_COSTS_PATH,
    )


def _check_openai_admin_endpoint(
    env: Mapping[str, str],
    timeout_seconds: float,
    http_get: HttpGet,
    *,
    name: str,
    path_env: str,
    default_path: str,
) -> dict[str, Any]:
    admin_key = env.get("CUSTOMER_AI_OPENAI_ADMIN_API_KEY")
    if not admin_key:
        return _skipped(name, "missing CUSTOMER_AI_OPENAI_ADMIN_API_KEY")
    base_url = (
        env.get("CUSTOMER_AI_OPENAI_ADMIN_BASE_URL") or DEFAULT_OPENAI_ADMIN_BASE_URL
    ).rstrip("/")
    path = env.get(path_env) or default_path
    url = f"{base_url}/{path.lstrip('/')}"
    return _get_json(
        name,
        url,
        timeout_seconds=timeout_seconds,
        headers={"Authorization": "Bearer ***"},
        request_headers={"Authorization": f"Bearer {admin_key}"},
        http_get=http_get,
    )


def _check_qdrant_health(
    env: Mapping[str, str],
    timeout_seconds: float,
    http_get: HttpGet,
) -> dict[str, Any]:
    url = env.get("CUSTOMER_AI_QDRANT_URL")
    if not url:
        return _skipped("qdrant_health", "missing CUSTOMER_AI_QDRANT_URL")
    credential = env.get("CUSTOMER_AI_QDRANT_API_KEY")
    request_headers = {"api-key": credential} if credential else {}
    safe_headers = {"api-key": "***"} if credential else {}
    return _get_json(
        "qdrant_health",
        f"{url.rstrip('/')}/healthz",
        timeout_seconds=timeout_seconds,
        headers=safe_headers,
        request_headers=request_headers,
        http_get=http_get,
    )


def _check_qdrant_collections(
    env: Mapping[str, str],
    timeout_seconds: float,
    http_get: HttpGet,
) -> dict[str, Any]:
    url = env.get("CUSTOMER_AI_QDRANT_URL")
    if not url:
        return _skipped("qdrant_collections", "missing CUSTOMER_AI_QDRANT_URL")
    credential = env.get("CUSTOMER_AI_QDRANT_API_KEY")
    request_headers = {"api-key": credential} if credential else {}
    safe_headers = {"api-key": "***"} if credential else {}
    return _get_json(
        "qdrant_collections",
        f"{url.rstrip('/')}/collections",
        timeout_seconds=timeout_seconds,
        headers=safe_headers,
        request_headers=request_headers,
        http_get=http_get,
    )


def _check_business_api(
    env: Mapping[str, str],
    timeout_seconds: float,
    http_get: HttpGet,
) -> dict[str, Any]:
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
        http_get=http_get,
    )


def _check_ticket_api(
    env: Mapping[str, str],
    timeout_seconds: float,
    http_get: HttpGet,
) -> dict[str, Any]:
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
        http_get=http_get,
    )


def _check_redis_queue(
    env: Mapping[str, str],
    timeout_seconds: float,
    tcp_connect: TcpConnect,
) -> dict[str, Any]:
    host = env.get("CUSTOMER_AI_REDIS_HOST")
    if not host:
        return _skipped("redis_queue", "missing CUSTOMER_AI_REDIS_HOST")
    port = int(env.get("CUSTOMER_AI_REDIS_PORT") or "6379")
    return _check_tcp("redis_queue", host, port, timeout_seconds, tcp_connect)


def _check_postgres_queue(
    env: Mapping[str, str],
    timeout_seconds: float,
    tcp_connect: TcpConnect,
) -> dict[str, Any]:
    host = env.get("CUSTOMER_AI_POSTGRES_HOST")
    if not host:
        return _skipped("postgres_queue", "missing CUSTOMER_AI_POSTGRES_HOST")
    port = int(env.get("CUSTOMER_AI_POSTGRES_PORT") or "5432")
    return _check_tcp("postgres_queue", host, port, timeout_seconds, tcp_connect)


def _get_json(
    name: str,
    url: str,
    *,
    timeout_seconds: float,
    headers: dict[str, str],
    request_headers: dict[str, str],
    http_get: HttpGet,
) -> dict[str, Any]:
    try:
        status_code = http_get(url, request_headers, timeout_seconds)
    except Exception as exc:
        return {
            "name": name,
            "status": "failed",
            "message": exc.__class__.__name__,
            "url": url,
            "headers": headers,
        }
    if status_code >= 400:
        return {
            "name": name,
            "status": "failed",
            "message": f"HTTP {status_code}",
            "url": url,
            "headers": headers,
        }
    return {
        "name": name,
        "status": "passed",
        "message": f"HTTP {status_code}",
        "url": url,
        "headers": headers,
    }


def _check_tcp(
    name: str,
    host: str,
    port: int,
    timeout_seconds: float,
    tcp_connect: TcpConnect,
) -> dict[str, Any]:
    endpoint = f"{host}:{port}"
    try:
        tcp_connect(host, port, timeout_seconds)
    except Exception as exc:
        return {
            "name": name,
            "status": "failed",
            "message": exc.__class__.__name__,
            "endpoint": endpoint,
        }
    return {
        "name": name,
        "status": "passed",
        "message": "tcp connected",
        "endpoint": endpoint,
    }


def _http_get(url: str, headers: dict[str, str], timeout_seconds: float) -> int:
    response = httpx.get(url, headers=headers, timeout=timeout_seconds)
    return response.status_code


def _tcp_connect(host: str, port: int, timeout_seconds: float) -> None:
    with socket.create_connection((host, port), timeout=timeout_seconds):
        return


def _skipped(name: str, message: str) -> dict[str, Any]:
    return {
        "name": name,
        "status": "skipped",
        "message": message,
    }


if __name__ == "__main__":
    raise SystemExit(main())
