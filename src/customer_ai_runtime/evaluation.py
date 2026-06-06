from __future__ import annotations

from typing import Any


def evaluate_rag_results(
    cases: list[dict[str, Any]],
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    result_by_id = {str(item.get("case_id")): item for item in results}
    evaluated_cases: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    effective_hits = 0
    labeled_count = 0
    labeled_passed_count = 0
    reviewed_count = 0
    cohort_stats: dict[str, dict[str, int]] = {}

    for case in cases:
        case_id = str(case.get("case_id") or "")
        result = result_by_id.get(case_id, {})
        citations = _citations(result)
        max_score = _max_citation_score(citations)
        min_score = float(case.get("min_score", 0.0))
        effective_hit = bool(citations) and max_score >= min_score
        expected_effective_hit = bool(case.get("expect_effective_hit", True))
        expected_route = str(case.get("expected_route") or "knowledge")
        actual_route = str(result.get("route") or "")
        missing_keywords = _missing_citation_keywords(
            citations,
            [str(keyword) for keyword in case.get("expected_citation_keywords", [])],
        )

        route_ok = actual_route == expected_route
        keywords_ok = not missing_keywords
        effective_hit_ok = effective_hit == expected_effective_hit
        passed = route_ok and keywords_ok and effective_hit_ok
        if effective_hit:
            effective_hits += 1
        dataset_id = str(case.get("dataset_id") or "local")
        cohort = str(case.get("cohort") or "default")
        review_status = str(case.get("review_status") or "unreviewed")
        labeled = _is_labeled_case(case)
        if labeled:
            labeled_count += 1
            if passed:
                labeled_passed_count += 1
        if review_status in {"reviewed", "approved", "rejected"}:
            reviewed_count += 1
        cohort_bucket = cohort_stats.setdefault(
            cohort,
            {
                "case_count": 0,
                "passed": 0,
                "failed": 0,
                "labeled_case_count": 0,
                "labeled_passed_count": 0,
                "reviewed_case_count": 0,
            },
        )
        cohort_bucket["case_count"] += 1
        cohort_bucket["passed"] += 1 if passed else 0
        cohort_bucket["failed"] += 0 if passed else 1
        cohort_bucket["labeled_case_count"] += 1 if labeled else 0
        cohort_bucket["labeled_passed_count"] += 1 if labeled and passed else 0
        cohort_bucket["reviewed_case_count"] += (
            1 if review_status in {"reviewed", "approved", "rejected"} else 0
        )

        item = {
            "case_id": case_id,
            "dataset_id": dataset_id,
            "cohort": cohort,
            "review_status": review_status,
            "question": case.get("question"),
            "route": actual_route,
            "expected_route": expected_route,
            "route_ok": route_ok,
            "citation_count": len(citations),
            "max_score": round(max_score, 4),
            "min_score": min_score,
            "effective_hit": effective_hit,
            "expected_effective_hit": expected_effective_hit,
            "effective_hit_ok": effective_hit_ok,
            "missing_keywords": missing_keywords,
            "keywords_ok": keywords_ok,
            "labeled": labeled,
            "passed": passed,
        }
        evaluated_cases.append(item)
        if not passed:
            failures.append(item)

    case_count = len(evaluated_cases)
    passed_count = sum(1 for item in evaluated_cases if item["passed"])
    return {
        "summary": {
            "case_count": case_count,
            "passed": passed_count,
            "failed": case_count - passed_count,
            "pass_rate": 0.0 if case_count == 0 else round(passed_count / case_count, 4),
            "effective_hit_rate": 0.0 if case_count == 0 else round(effective_hits / case_count, 4),
            "labeled_case_count": labeled_count,
            "reviewed_case_count": reviewed_count,
            "offline_accuracy": 0.0
            if labeled_count == 0
            else round(labeled_passed_count / labeled_count, 4),
            "cohort_breakdown": _cohort_breakdown(cohort_stats),
        },
        "cases": evaluated_cases,
        "failures": failures,
    }


def _citations(result: dict[str, Any]) -> list[dict[str, Any]]:
    raw_citations = result.get("citations")
    if not isinstance(raw_citations, list):
        return []
    return [item for item in raw_citations if isinstance(item, dict)]


def _max_citation_score(citations: list[dict[str, Any]]) -> float:
    scores: list[float] = []
    for citation in citations:
        try:
            scores.append(float(citation.get("score") or 0.0))
        except (TypeError, ValueError):
            continue
    return max(scores, default=0.0)


def _missing_citation_keywords(
    citations: list[dict[str, Any]],
    expected_keywords: list[str],
) -> list[str]:
    citation_text = " ".join(
        str(citation.get(field) or "")
        for citation in citations
        for field in ("title", "excerpt", "content")
    ).lower()
    return [
        keyword
        for keyword in expected_keywords
        if keyword.strip() and keyword.strip().lower() not in citation_text
    ]


def _is_labeled_case(case: dict[str, Any]) -> bool:
    if "label" in case:
        return True
    return any(
        key in case
        for key in (
            "expected_route",
            "expected_citation_keywords",
            "expect_effective_hit",
            "min_score",
        )
    )


def _cohort_breakdown(cohort_stats: dict[str, dict[str, int]]) -> dict[str, dict[str, Any]]:
    return {
        cohort: {
            **stats,
            "pass_rate": 0.0
            if stats["case_count"] == 0
            else round(stats["passed"] / stats["case_count"], 4),
            "offline_accuracy": 0.0
            if stats["labeled_case_count"] == 0
            else round(stats["labeled_passed_count"] / stats["labeled_case_count"], 4),
        }
        for cohort, stats in sorted(cohort_stats.items())
    }
