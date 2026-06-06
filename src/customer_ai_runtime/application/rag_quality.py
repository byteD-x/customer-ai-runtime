from __future__ import annotations

from pydantic import BaseModel, Field

from customer_ai_runtime.application.runtime import zh
from customer_ai_runtime.core.text import tokenize_text
from customer_ai_runtime.domain.models import Citation


class HallucinationCheckResult(BaseModel):
    passed: bool
    refusal: bool = False
    reason: str = ""
    faithfulness_score: float = 0.0
    evidence_token_overlap: float = 0.0
    citation_count: int = 0
    effective_citation_count: int = 0
    checked_claim_terms: list[str] = Field(default_factory=list)
    unsupported_terms: list[str] = Field(default_factory=list)


class HallucinationCheckService:
    def __init__(self, *, min_overlap: float = 0.08) -> None:
        self._min_overlap = min_overlap

    def check(
        self,
        *,
        answer: str,
        citations: list[Citation],
        effective_hit_count: int,
    ) -> HallucinationCheckResult:
        citation_count = len(citations)
        if citation_count == 0 or effective_hit_count <= 0:
            return HallucinationCheckResult(
                passed=False,
                refusal=True,
                reason="no_effective_citation",
                citation_count=citation_count,
                effective_citation_count=effective_hit_count,
            )

        answer_terms = self._content_terms(answer)
        evidence_terms = self._content_terms(
            " ".join(
                part
                for citation in citations
                for part in (
                    citation.title,
                    citation.excerpt,
                    citation.source or "",
                    citation.source_url or "",
                )
            )
        )
        if not answer_terms:
            return HallucinationCheckResult(
                passed=False,
                refusal=True,
                reason="empty_answer",
                citation_count=citation_count,
                effective_citation_count=effective_hit_count,
            )

        supported_terms = [term for term in answer_terms if term in evidence_terms]
        unsupported_terms = [term for term in answer_terms if term not in evidence_terms]
        overlap = round(len(supported_terms) / len(answer_terms), 4)
        passed = overlap >= self._min_overlap
        return HallucinationCheckResult(
            passed=passed,
            refusal=not passed,
            reason="passed" if passed else "low_evidence_overlap",
            faithfulness_score=overlap,
            evidence_token_overlap=overlap,
            citation_count=citation_count,
            effective_citation_count=effective_hit_count,
            checked_claim_terms=answer_terms[:30],
            unsupported_terms=unsupported_terms[:30],
        )

    def refusal_answer(self) -> str:
        return zh(
            "\\u5f53\\u524d\\u77e5\\u8bc6\\u5e93\\u6ca1\\u6709\\u627e\\u5230"
            "\\u8db3\\u591f\\u53ef\\u9760\\u7684\\u4f9d\\u636e\\uff0c\\u6211"
            "\\u4e0d\\u4f1a\\u731c\\u6d4b\\u7b54\\u6848\\u3002\\u8bf7\\u8865"
            "\\u5145\\u66f4\\u5177\\u4f53\\u7684\\u95ee\\u9898\\uff0c\\u6216\\u8054"
            "\\u7cfb\\u4eba\\u5de5\\u5ba2\\u670d\\u5904\\u7406\\u3002"
        )

    def _content_terms(self, text: str) -> list[str]:
        seen: set[str] = set()
        terms: list[str] = []
        for token in tokenize_text(text):
            if token.isdigit() or token in seen:
                continue
            if len(token) < 2 and not self._is_cjk_term(token):
                continue
            seen.add(token)
            terms.append(token)
        return terms

    def _is_cjk_term(self, term: str) -> bool:
        return any("\u4e00" <= char <= "\u9fff" for char in term)
