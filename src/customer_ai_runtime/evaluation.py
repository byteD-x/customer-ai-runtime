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
    citation_accuracy_values: list[float] = []
    refusal_checked_count = 0
    refusal_passed_count = 0
    faithfulness_scores: list[float] = []

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
        expected_citation_keywords = [
            str(keyword) for keyword in case.get("expected_citation_keywords", [])
        ]
        missing_keywords = _missing_citation_keywords(
            citations,
            expected_citation_keywords,
        )
        citation_accuracy = _citation_accuracy(missing_keywords, expected_citation_keywords)
        expected_refusal = _expects_refusal(case)
        actual_refusal = _is_refusal(result)
        refusal_ok = actual_refusal == expected_refusal if expected_refusal is not None else None
        faithfulness_score = _faithfulness_score(result, citations, missing_keywords)

        route_ok = actual_route == expected_route
        keywords_ok = not missing_keywords
        effective_hit_ok = effective_hit == expected_effective_hit
        passed = route_ok and keywords_ok and effective_hit_ok
        if refusal_ok is not None:
            passed = passed and refusal_ok
        if effective_hit:
            effective_hits += 1
        if citation_accuracy is not None:
            citation_accuracy_values.append(citation_accuracy)
        if refusal_ok is not None:
            refusal_checked_count += 1
            refusal_passed_count += 1 if refusal_ok else 0
        if faithfulness_score is not None:
            faithfulness_scores.append(faithfulness_score)
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
            "citation_accuracy": citation_accuracy,
            "expected_refusal": expected_refusal,
            "actual_refusal": actual_refusal,
            "refusal_ok": refusal_ok,
            "faithfulness_score": faithfulness_score,
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
            "citation_accuracy": _average(citation_accuracy_values),
            "refusal_accuracy": 0.0
            if refusal_checked_count == 0
            else round(refusal_passed_count / refusal_checked_count, 4),
            "refusal_case_count": refusal_checked_count,
            "faithfulness_score": _average(faithfulness_scores),
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
        for field in ("title", "excerpt", "content", "source", "source_url")
    ).lower()
    return [
        keyword
        for keyword in expected_keywords
        if keyword.strip() and keyword.strip().lower() not in citation_text
    ]


def _citation_accuracy(
    missing_keywords: list[str],
    expected_keywords: list[str],
) -> float | None:
    normalized = [keyword for keyword in expected_keywords if keyword.strip()]
    if not normalized:
        return None
    matched = len(normalized) - len(missing_keywords)
    return round(max(0.0, matched / len(normalized)), 4)


def _expects_refusal(case: dict[str, Any]) -> bool | None:
    if "expect_refusal" in case:
        return bool(case.get("expect_refusal"))
    label = case.get("label")
    expected_answer_type = ""
    if isinstance(label, dict):
        expected_answer_type = str(label.get("expected_answer_type") or "")
    if expected_answer_type in {"no_effective_hit", "refusal"}:
        return True
    if case.get("expect_effective_hit") is False:
        return True
    return None


def _is_refusal(result: dict[str, Any]) -> bool:
    if result.get("refusal") is True:
        return True
    if result.get("refusal_reason"):
        return True
    check = result.get("hallucination_check")
    if isinstance(check, dict) and check.get("refusal") is True:
        return True
    return False


def _faithfulness_score(
    result: dict[str, Any],
    citations: list[dict[str, Any]],
    missing_keywords: list[str],
) -> float | None:
    check = result.get("hallucination_check")
    if isinstance(check, dict):
        raw_score = check.get("faithfulness_score")
        try:
            return round(float(raw_score), 4)
        except (TypeError, ValueError):
            pass
    expected_count = len(missing_keywords)
    citation_count = len(citations)
    if citation_count == 0:
        return None
    if expected_count == 0:
        return 1.0
    return 0.0


def _average(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 4)


def _is_labeled_case(case: dict[str, Any]) -> bool:
    if "label" in case:
        return True
    return any(
        key in case
        for key in (
            "expected_route",
            "expected_citation_keywords",
            "expect_effective_hit",
            "expect_refusal",
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
