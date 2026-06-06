from __future__ import annotations

from threading import RLock
from typing import Protocol

from customer_ai_runtime.application.session import SessionService
from customer_ai_runtime.domain.models import Session, SessionState, utcnow


class HandoffQueueBackend(Protocol):
    name: str
    atomic_claim: bool
    consistency_scope: str

    def enqueue(
        self,
        session: Session,
        *,
        reason: str,
        skill_group: str,
        priority: int,
    ) -> Session: ...

    def list_waiting(
        self,
        tenant_id: str,
        skill_group: str | None = None,
    ) -> list[Session]: ...

    def claim_next(
        self,
        tenant_id: str,
        skill_group: str | None = None,
        operator_id: str | None = None,
    ) -> Session | None: ...


class LocalHandoffQueueBackend:
    name = "local"
    atomic_claim = True
    consistency_scope = "single_process"

    def __init__(self, session_service: SessionService) -> None:
        self._session_service = session_service
        self._lock = RLock()

    def enqueue(
        self,
        session: Session,
        *,
        reason: str,
        skill_group: str,
        priority: int,
    ) -> Session:
        with self._lock:
            session.state = SessionState.WAITING_HUMAN
            session.waiting_human = True
            session.handoff_reason = reason
            session.handoff_skill_group = skill_group
            session.handoff_priority = priority
            session.handoff_enqueued_at = session.handoff_enqueued_at or utcnow()
            session.assigned_operator_id = None
            return self._session_service.save(session)

    def list_waiting(
        self,
        tenant_id: str,
        skill_group: str | None = None,
    ) -> list[Session]:
        return _sort_waiting_sessions(
            [
                session
                for session in self._session_service.list_by_tenant(tenant_id)
                if _matches_waiting_queue(session, skill_group)
            ]
        )

    def claim_next(
        self,
        tenant_id: str,
        skill_group: str | None = None,
        operator_id: str | None = None,
    ) -> Session | None:
        with self._lock:
            sessions = self.list_waiting(tenant_id, skill_group)
            if not sessions:
                return None
            candidate = sessions[0]
            current = self._session_service.get(tenant_id, candidate.session_id)
            if not _matches_waiting_queue(current, skill_group):
                return None
            return self._session_service.claim_human(
                tenant_id,
                current.session_id,
                operator_id=operator_id,
            )


def _matches_waiting_queue(session: Session, skill_group: str | None) -> bool:
    if not session.waiting_human:
        return False
    if skill_group and session.handoff_skill_group != skill_group:
        return False
    return True


def _sort_waiting_sessions(sessions: list[Session]) -> list[Session]:
    return sorted(
        sessions,
        key=lambda session: (
            -session.handoff_priority,
            session.handoff_enqueued_at or session.updated_at,
        ),
    )
