from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from threading import RLock
from typing import Protocol

from customer_ai_runtime.application.session import SessionService
from customer_ai_runtime.core.errors import AppError
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


class SQLiteHandoffQueueBackend:
    name = "sqlite"
    atomic_claim = True
    consistency_scope = "shared_sqlite_queue"

    def __init__(self, session_service: SessionService, storage_root: str | Path) -> None:
        self._session_service = session_service
        state_dir = Path(storage_root) / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = state_dir / "handoff_queue.sqlite3"
        self._ensure_schema()

    def enqueue(
        self,
        session: Session,
        *,
        reason: str,
        skill_group: str,
        priority: int,
    ) -> Session:
        session.state = SessionState.WAITING_HUMAN
        session.waiting_human = True
        session.handoff_reason = reason
        session.handoff_skill_group = skill_group
        session.handoff_priority = priority
        session.handoff_enqueued_at = session.handoff_enqueued_at or utcnow()
        session.assigned_operator_id = None
        saved = self._session_service.save(session)
        now = utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO handoff_queue (
                    tenant_id, session_id, skill_group, priority, enqueued_at,
                    status, reason, operator_id, claimed_at, session_snapshot, updated_at
                )
                VALUES (?, ?, ?, ?, ?, 'waiting', ?, NULL, NULL, ?, ?)
                ON CONFLICT(tenant_id, session_id) DO UPDATE SET
                    skill_group = excluded.skill_group,
                    priority = excluded.priority,
                    enqueued_at = excluded.enqueued_at,
                    status = 'waiting',
                    reason = excluded.reason,
                    operator_id = NULL,
                    claimed_at = NULL,
                    session_snapshot = excluded.session_snapshot,
                    updated_at = excluded.updated_at
                """,
                (
                    saved.tenant_id,
                    saved.session_id,
                    saved.handoff_skill_group,
                    saved.handoff_priority,
                    _datetime_key(saved),
                    saved.handoff_reason,
                    _session_snapshot(saved),
                    now,
                ),
            )
        return saved

    def list_waiting(
        self,
        tenant_id: str,
        skill_group: str | None = None,
    ) -> list[Session]:
        sessions: list[Session] = []
        with self._connect() as conn:
            rows = self._waiting_rows(conn, tenant_id, skill_group)
            for row in rows:
                candidate = self._resolve_waiting_session(row, skill_group)
                if candidate is None:
                    self._mark_stale(conn, row)
                    continue
                sessions.append(candidate)
        return _sort_waiting_sessions(sessions)

    def claim_next(
        self,
        tenant_id: str,
        skill_group: str | None = None,
        operator_id: str | None = None,
    ) -> Session | None:
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            while True:
                row = self._first_waiting_row(conn, tenant_id, skill_group)
                if row is None:
                    conn.execute("COMMIT")
                    return None
                candidate = self._resolve_waiting_session(row, skill_group)
                if candidate is None:
                    self._mark_stale(conn, row)
                    continue

                self._session_service.save(candidate)
                claimed = self._session_service.claim_human(
                    candidate.tenant_id,
                    candidate.session_id,
                    operator_id=operator_id,
                )
                now = utcnow().isoformat()
                conn.execute(
                    """
                    UPDATE handoff_queue
                    SET status = 'claimed',
                        operator_id = ?,
                        claimed_at = ?,
                        session_snapshot = ?,
                        updated_at = ?
                    WHERE tenant_id = ? AND session_id = ?
                    """,
                    (
                        operator_id,
                        now,
                        _session_snapshot(claimed),
                        now,
                        claimed.tenant_id,
                        claimed.session_id,
                    ),
                )
                conn.execute("COMMIT")
                return claimed
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS handoff_queue (
                    tenant_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    skill_group TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    enqueued_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    operator_id TEXT,
                    claimed_at TEXT,
                    session_snapshot TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, session_id)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_handoff_queue_waiting
                ON handoff_queue (tenant_id, status, skill_group, priority DESC, enqueued_at ASC)
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _waiting_rows(
        self,
        conn: sqlite3.Connection,
        tenant_id: str,
        skill_group: str | None,
    ) -> list[sqlite3.Row]:
        if skill_group:
            return list(
                conn.execute(
                    """
                    SELECT *
                    FROM handoff_queue
                    WHERE tenant_id = ? AND status = 'waiting' AND skill_group = ?
                    ORDER BY priority DESC, enqueued_at ASC
                    """,
                    (tenant_id, skill_group),
                )
            )
        return list(
            conn.execute(
                """
                SELECT *
                FROM handoff_queue
                WHERE tenant_id = ? AND status = 'waiting'
                ORDER BY priority DESC, enqueued_at ASC
                """,
                (tenant_id,),
            )
        )

    def _first_waiting_row(
        self,
        conn: sqlite3.Connection,
        tenant_id: str,
        skill_group: str | None,
    ) -> sqlite3.Row | None:
        rows = self._waiting_rows(conn, tenant_id, skill_group)
        return rows[0] if rows else None

    def _resolve_waiting_session(
        self,
        row: sqlite3.Row,
        skill_group: str | None,
    ) -> Session | None:
        snapshot = Session.model_validate(json.loads(str(row["session_snapshot"])))
        try:
            current = self._session_service.get(snapshot.tenant_id, snapshot.session_id)
        except AppError:
            current = snapshot
        return current if _matches_waiting_queue(current, skill_group) else None

    def _mark_stale(self, conn: sqlite3.Connection, row: sqlite3.Row) -> None:
        conn.execute(
            """
            UPDATE handoff_queue
            SET status = 'stale', updated_at = ?
            WHERE tenant_id = ? AND session_id = ?
            """,
            (utcnow().isoformat(), str(row["tenant_id"]), str(row["session_id"])),
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


def _datetime_key(session: Session) -> str:
    return (session.handoff_enqueued_at or session.updated_at).isoformat()


def _session_snapshot(session: Session) -> str:
    return json.dumps(session.model_dump(mode="json"), ensure_ascii=False)
