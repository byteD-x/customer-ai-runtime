from __future__ import annotations

from customer_ai_runtime.core.text import tokenize_text
from customer_ai_runtime.domain.models import Citation, RetrievalHit


class RerankService:
    def rerank(
        self,
        *,
        query: str,
        hits: list[RetrievalHit],
        top_k: int,
    ) -> list[RetrievalHit]:
        query_terms = set(tokenize_text(query))
        if not query_terms:
            return hits[:top_k]
        reranked = [
            hit.model_copy(update={"score": self._hybrid_score(query_terms, hit)}) for hit in hits
        ]
        reranked.sort(key=lambda item: (-item.score, item.chunk.source or "", item.chunk.position))
        return reranked[:top_k]

    def _hybrid_score(self, query_terms: set[str], hit: RetrievalHit) -> float:
        content_terms = set(tokenize_text(f"{hit.chunk.title} {hit.chunk.content}"))
        lexical_overlap = (
            0.0 if not content_terms else len(query_terms & content_terms) / len(query_terms)
        )
        return round(min(1.0, hit.score * 0.75 + lexical_overlap * 0.25), 4)


class CitationService:
    def from_hits(self, hits: list[RetrievalHit]) -> list[Citation]:
        return [
            Citation(
                knowledge_base_id=hit.chunk.knowledge_base_id,
                version_id=hit.chunk.version_id,
                document_id=hit.chunk.document_id,
                title=hit.chunk.title,
                chunk_id=hit.chunk.chunk_id,
                score=round(hit.score, 4),
                excerpt=hit.chunk.content,
                source=hit.chunk.source,
                source_url=hit.chunk.source_url,
                page=hit.chunk.page,
                metadata=dict(hit.chunk.metadata),
            )
            for hit in hits
        ]


class RetrievalService:
    def __init__(
        self,
        *,
        reranker: RerankService | None = None,
        citation_service: CitationService | None = None,
    ) -> None:
        self._reranker = reranker or RerankService()
        self._citation_service = citation_service or CitationService()

    def to_citations(
        self,
        *,
        query: str,
        hits: list[RetrievalHit],
        top_k: int,
    ) -> list[Citation]:
        reranked_hits = self._reranker.rerank(query=query, hits=hits, top_k=top_k)
        return self._citation_service.from_hits(reranked_hits)
