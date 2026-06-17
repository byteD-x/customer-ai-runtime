from __future__ import annotations

import argparse
import json
import os
import socket
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

DEFAULT_TIMEOUT_SECONDS = 5.0
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_OPENAI_ADMIN_BASE_URL = "https://api.openai.com/v1"
DEFAULT_OPENAI_ADMIN_USAGE_PATH = "/organization/usage/completions?limit=1"
DEFAULT_OPENAI_ADMIN_COSTS_PATH = "/organization/costs?limit=1"

HttpGet = Callable[[str, dict[str, str], float], int]
TcpConnect = Callable[[str, int, float], None]

CHECK_AUDIT: dict[str, dict[str, Any]] = {
    "openai_models": {
        "category": "llm_provider",
        "probe_type": "http_get",
        "required_env": ["CUSTOMER_AI_OPENAI_API_KEY"],
        "optional_env": ["CUSTOMER_AI_OPENAI_BASE_URL"],
    },
    "openai_admin_usage": {
        "category": "billing_provider",
        "probe_type": "http_get",
        "required_env": ["CUSTOMER_AI_OPENAI_ADMIN_API_KEY"],
        "optional_env": [
            "CUSTOMER_AI_OPENAI_ADMIN_BASE_URL",
            "CUSTOMER_AI_OPENAI_ADMIN_USAGE_PATH",
        ],
    },
    "openai_admin_costs": {
        "category": "billing_provider",
        "probe_type": "http_get",
        "required_env": ["CUSTOMER_AI_OPENAI_ADMIN_API_KEY"],
        "optional_env": [
            "CUSTOMER_AI_OPENAI_ADMIN_BASE_URL",
            "CUSTOMER_AI_OPENAI_ADMIN_COSTS_PATH",
        ],
    },
    "qdrant_runtime_config": {
        "category": "vector_store",
        "probe_type": "configuration",
        "required_env": [],
        "optional_env": [
            "CUSTOMER_AI_VECTOR_PROVIDER",
            "CUSTOMER_AI_QDRANT_URL",
        ],
    },
    "qdrant_health": {
        "category": "vector_store",
        "probe_type": "http_get",
        "required_env": ["CUSTOMER_AI_QDRANT_URL"],
        "optional_env": ["CUSTOMER_AI_QDRANT_API_KEY"],
    },
    "qdrant_collections": {
        "category": "vector_store",
        "probe_type": "http_get",
        "required_env": ["CUSTOMER_AI_QDRANT_URL"],
        "optional_env": ["CUSTOMER_AI_QDRANT_API_KEY"],
    },
    "business_api": {
        "category": "business_system",
        "probe_type": "http_get",
        "required_env": ["CUSTOMER_AI_BUSINESS_API_BASE_URL"],
        "optional_env": ["CUSTOMER_AI_BUSINESS_API_KEY"],
    },
    "ticket_api": {
        "category": "ticket_system",
        "probe_type": "http_get",
        "required_env": ["CUSTOMER_AI_TICKET_API_BASE_URL"],
        "optional_env": ["CUSTOMER_AI_TICKET_API_KEY"],
    },
    "redis_queue": {
        "category": "queue_dependency",
        "probe_type": "tcp_connect",
        "required_env": ["CUSTOMER_AI_REDIS_HOST"],
        "optional_env": ["CUSTOMER_AI_REDIS_PORT"],
    },
    "postgres_queue": {
        "category": "queue_dependency",
        "probe_type": "tcp_connect",
        "required_env": ["CUSTOMER_AI_POSTGRES_HOST"],
        "optional_env": ["CUSTOMER_AI_POSTGRES_PORT"],
    },
}


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
        _check_qdrant_runtime_config(env),
        _check_qdrant_health(env, timeout_seconds, http_get),
        _check_qdrant_collections(env, timeout_seconds, http_get),
        _check_business_api(env, timeout_seconds, http_get),
        _check_ticket_api(env, timeout_seconds, http_get),
        _check_redis_queue(env, timeout_seconds, tcp_connect),
        _check_postgres_queue(env, timeout_seconds, tcp_connect),
    ]
    _attach_audits(checks)

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
        "audit": {
            "scope": "optional_external_integration_readiness",
            "generated_at": _utc_now(),
            "timeout_seconds": timeout_seconds,
            "evidence_level": "configuration_and_probe",
            "disclaimer": (
                "Readiness checks verify optional configuration, HTTP/TCP reachability, "
                "and limited permission probes only; they do not prove end-to-end integration."
            ),
        },
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check optional external integration readiness.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--output", type=Path, default=None, help="Write the report to a UTF-8 file.")
    args = parser.parse_args()

    report = run_checks(timeout_seconds=args.timeout)
    output_text = _render_output(report, json_output=args.json)
    if args.output is not None:
        write_output_file(args.output, output_text)
        print(f"wrote_report: {args.output}")
    else:
        print(output_text, end="")
    return 1 if report["overall_status"] == "failed" else 0


def write_output_file(output_path: Path, output_text: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(output_text, encoding="utf-8")


def _render_output(report: dict[str, Any], *, json_output: bool) -> str:
    if json_output:
        return json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    lines = ["external_readiness"]
    audit = report["audit"]
    lines.append(f"scope: {audit['scope']}")
    lines.append(f"evidence_level: {audit['evidence_level']}")
    lines.append(f"timeout_seconds: {audit['timeout_seconds']}")
    for check in report["checks"]:
        lines.append(f"- {check['name']}: {check['status']} ({check['message']})")
        check_audit = check["audit"]
        lines.append(
            "  "
            f"category={check_audit['category']}; "
            f"probe_type={check_audit['probe_type']}; "
            f"required_env={','.join(check_audit['required_env']) or '-'}"
        )
    lines.append(f"overall_status: {report['overall_status']}")
    lines.append(f"disclaimer: {audit['disclaimer']}")
    return "\n".join(lines) + "\n"


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


def _check_qdrant_runtime_config(env: Mapping[str, str]) -> dict[str, Any]:
    vector_provider = (env.get("CUSTOMER_AI_VECTOR_PROVIDER") or "local").strip().lower()
    if not vector_provider:
        vector_provider = "local"
    if vector_provider != "qdrant":
        return {
            "name": "qdrant_runtime_config",
            "status": "skipped",
            "message": f"CUSTOMER_AI_VECTOR_PROVIDER={vector_provider} does not enable Qdrant",
            "vector_provider": vector_provider,
        }
    if not env.get("CUSTOMER_AI_QDRANT_URL"):
        return {
            "name": "qdrant_runtime_config",
            "status": "failed",
            "message": "missing CUSTOMER_AI_QDRANT_URL while CUSTOMER_AI_VECTOR_PROVIDER=qdrant",
            "vector_provider": vector_provider,
        }
    return {
        "name": "qdrant_runtime_config",
        "status": "passed",
        "message": "Qdrant vector provider is enabled and CUSTOMER_AI_QDRANT_URL is configured",
        "vector_provider": vector_provider,
    }


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


def _attach_audits(checks: list[dict[str, Any]]) -> None:
    for check in checks:
        metadata = CHECK_AUDIT[str(check["name"])]
        audit = dict(metadata)
        audit["evidence"] = _audit_evidence(
            status=str(check["status"]),
            message=str(check["message"]),
            probe_type=str(metadata["probe_type"]),
        )
        check["audit"] = audit


def _audit_evidence(*, status: str, message: str, probe_type: str) -> str:
    if probe_type == "configuration":
        if status == "passed":
            return "configuration_consistent"
        if status == "failed":
            return "configuration_mismatch"
        if "does not enable Qdrant" in message:
            return "provider_not_enabled"
        return "missing_required_env"
    if status == "skipped":
        return "missing_required_env"
    if probe_type == "tcp_connect":
        return "tcp_connection" if status == "passed" else "tcp_exception"
    if status == "failed" and not message.startswith("HTTP "):
        return "http_exception"
    return "http_status_code"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
