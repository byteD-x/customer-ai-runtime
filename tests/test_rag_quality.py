from __future__ import annotations

from customer_ai_runtime.application.rag_quality import HallucinationCheckService
from customer_ai_runtime.application.retrieval import RerankService
from customer_ai_runtime.domain.models import Citation, KnowledgeChunk, RetrievalHit


def test_hallucination_check_passes_when_answer_is_supported() -> None:
    service = HallucinationCheckService()
    citation = Citation(
        knowledge_base_id="kb_support",
        version_id="kbver_1",
        document_id="doc_1",
        title="refund policy",
        chunk_id="chunk_1",
        score=0.72,
        excerpt="Refund requests need order id and payment proof.",
        source="help-center",
    )

    result = service.check(
        answer="Refund requests need payment proof.",
        citations=[citation],
        effective_hit_count=1,
    )

    assert result.passed is True
    assert result.refusal is False
    assert result.reason == "passed"
    assert result.faithfulness_score > 0


def test_hallucination_check_refuses_without_effective_citations() -> None:
    service = HallucinationCheckService()

    result = service.check(
        answer="Refund requests are handled quickly.",
        citations=[],
        effective_hit_count=0,
    )

    assert result.passed is False
    assert result.refusal is True
    assert result.reason == "no_effective_citation"
    assert result.effective_citation_count == 0


def test_hallucination_check_handles_chinese_evidence_terms() -> None:
    service = HallucinationCheckService()
    citation = Citation(
        knowledge_base_id="kb_support",
        version_id="kbver_1",
        document_id="doc_1",
        title="退款规则",
        chunk_id="chunk_1",
        score=0.8,
        excerpt="七天无理由退款，售后工单 24 小时内响应。",
        source="help-center",
    )

    result = service.check(
        answer="七天无理由退款，售后工单 24 小时内响应。",
        citations=[citation],
        effective_hit_count=1,
    )

    assert result.passed is True
    assert result.refusal is False
    assert "七" in result.checked_claim_terms


def test_rerank_keeps_stable_source_and_position_order_for_tied_scores() -> None:
    hits = [
        _retrieval_hit(source="support", position=2),
        _retrieval_hit(source="support", position=1),
        _retrieval_hit(source="billing", position=1),
    ]

    reranked = RerankService().rerank(
        query="refund",
        hits=hits,
        top_k=3,
    )

    assert [(item.chunk.source, item.chunk.position) for item in reranked] == [
        ("billing", 1),
        ("support", 1),
        ("support", 2),
    ]


def _retrieval_hit(*, source: str, position: int) -> RetrievalHit:
    return RetrievalHit(
        score=0.8,
        chunk=KnowledgeChunk(
            tenant_id="demo-tenant",
            knowledge_base_id="kb_support",
            version_id="kbver_1",
            document_id=f"doc_{source}_{position}",
            title="refund",
            content="refund",
            position=position,
            source=source,
        ),
    )
