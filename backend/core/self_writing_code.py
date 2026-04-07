"""
Self-Writing Code System — engineering agents propose code improvements.

Pipeline:
1. Detect inefficiency (via profiling, error patterns, or agent suggestions)
2. Generate improved code proposal
3. Test in sandbox (run existing tests)
4. Benchmark results
5. Deploy if improvement verified

Major system rewrites require Yohan approval.
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from backend.config import DATA_DIR

SELF_CODE_DB = DATA_DIR / "self_code.db"

logger = logging.getLogger("root.self_code")


class ProposalStatus(str, Enum):
    PROPOSED = "proposed"       # Initial proposal
    TESTING = "testing"         # Under sandbox testing
    APPROVED = "approved"       # Approved (auto or manual)
    DEPLOYED = "deployed"       # Code change applied
    REJECTED = "rejected"       # Failed tests or rejected by Yohan
    PENDING_APPROVAL = "pending_approval"  # Major change — needs Yohan


class ProposalScope(str, Enum):
    MINOR = "minor"             # Small optimization, auto-approvable
    MODERATE = "moderate"       # Meaningful change, auto-approve if tests pass
    MAJOR = "major"             # Architecture change — requires Yohan approval


@dataclass(frozen=True)
class CodeProposal:
    """Immutable code improvement proposal."""
    id: str
    title: str
    description: str
    file_path: str
    scope: ProposalScope
    status: ProposalStatus = ProposalStatus.PROPOSED
    inefficiency_detected: str = ""
    proposed_change: str = ""
    test_result: Optional[str] = None
    benchmark_before: Optional[str] = None
    benchmark_after: Optional[str] = None
    improvement_pct: Optional[float] = None
    agent_id: str = "system"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resolved_at: Optional[str] = None


class SelfWritingCodeSystem:
    """Manages code improvement proposals from engineering agents."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._db_path = str(db_path or SELF_CODE_DB)
        self._conn: Optional[sqlite3.Connection] = None
        self._approval_chain = None
        self._experience_memory = None
        self._sandbox_gate = None  # Set via main.py

    def set_approval_chain(self, approval) -> None:
        self._approval_chain = approval

    def set_experience_memory(self, exp_mem) -> None:
        self._experience_memory = exp_mem

    # ── Lifecycle ──────────────────────────────────────────────

    def start(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._create_tables()

    def stop(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("SelfWritingCodeSystem not started")
        return self._conn

    def _create_tables(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS code_proposals (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                file_path TEXT NOT NULL,
                scope TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'proposed',
                inefficiency_detected TEXT DEFAULT '',
                proposed_change TEXT DEFAULT '',
                test_result TEXT,
                benchmark_before TEXT,
                benchmark_after TEXT,
                improvement_pct REAL,
                agent_id TEXT DEFAULT 'system',
                created_at TEXT NOT NULL,
                resolved_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_cp_status ON code_proposals(status);
            CREATE INDEX IF NOT EXISTS idx_cp_scope ON code_proposals(scope);
        """)

    # ── Proposal Lifecycle ─────────────────────────────────────

    def propose_improvement(
        self,
        title: str,
        description: str,
        file_path: str,
        inefficiency: str,
        proposed_change: str,
        scope: str = "minor",
        agent_id: str = "system",
    ) -> CodeProposal:
        """Submit a code improvement proposal."""
        prop_scope = ProposalScope(scope)
        prop_id = f"cp_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        self.conn.execute(
            """INSERT INTO code_proposals
               (id, title, description, file_path, scope, status,
                inefficiency_detected, proposed_change, agent_id, created_at)
               VALUES (?, ?, ?, ?, ?, 'proposed', ?, ?, ?, ?)""",
            (prop_id, title, description, file_path, prop_scope.value,
             inefficiency, proposed_change, agent_id, now),
        )
        self.conn.commit()
        logger.info("Code proposal: %s — %s [%s]", prop_id, title, prop_scope.value)

        return CodeProposal(
            id=prop_id, title=title, description=description,
            file_path=file_path, scope=prop_scope,
            inefficiency_detected=inefficiency,
            proposed_change=proposed_change,
            agent_id=agent_id, created_at=now,
        )

    def record_test_result(
        self,
        proposal_id: str,
        test_passed: bool,
        test_output: str,
        benchmark_before: Optional[str] = None,
        benchmark_after: Optional[str] = None,
        improvement_pct: Optional[float] = None,
    ) -> Optional[CodeProposal]:
        """Record sandbox test results for a proposal."""
        now = datetime.now(timezone.utc).isoformat()

        if not test_passed:
            self.conn.execute(
                """UPDATE code_proposals
                   SET status = 'rejected', test_result = ?, resolved_at = ?
                   WHERE id = ?""",
                (test_output, now, proposal_id),
            )
            self.conn.commit()
            logger.info("Proposal rejected (test failed): %s", proposal_id)
            self._record_lesson(proposal_id, success=False)
            return self._get_by_id(proposal_id)

        # Tests passed — determine next status based on scope
        row = self.conn.execute(
            "SELECT scope FROM code_proposals WHERE id = ?", (proposal_id,),
        ).fetchone()
        if not row:
            return None

        scope = ProposalScope(row["scope"])
        if scope == ProposalScope.MAJOR:
            new_status = "pending_approval"
        else:
            new_status = "approved"

        self.conn.execute(
            """UPDATE code_proposals
               SET status = ?, test_result = ?, benchmark_before = ?,
                   benchmark_after = ?, improvement_pct = ?
               WHERE id = ?""",
            (new_status, test_output, benchmark_before,
             benchmark_after, improvement_pct, proposal_id),
        )
        self.conn.commit()
        logger.info("Proposal %s: %s", new_status, proposal_id)

        # Auto-deploy MINOR proposals that pass tests
        if hasattr(self, '_deployment_pipeline') and self._deployment_pipeline:
            if scope in (ProposalScope.MINOR,) and new_status == "approved":
                try:
                    import asyncio
                    proposal = self._get_by_id(proposal_id)
                    if proposal:
                        loop = asyncio.get_running_loop()
                        task = loop.create_task(self._auto_deploy(proposal))
                        task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)
                except RuntimeError:
                    logger.debug("No running event loop — skipping auto-deploy scheduling")
                except Exception as e:
                    logger.warning("Code auto-deploy scheduling failed: %s", e)

        return self._get_by_id(proposal_id)

    async def _auto_deploy(self, proposal: CodeProposal) -> None:
        """Auto-deploy a MINOR proposal via the deployment pipeline."""
        try:
            deploy_result = await self._deployment_pipeline.deploy_proposal(
                file_path=proposal.file_path,
                original_content="",
                proposed_content=proposal.proposed_change,
                proposal_id=proposal.id,
            )
            if deploy_result.success:
                self.mark_deployed(proposal.id)
                logger.info("Auto-deployed MINOR proposal %s", proposal.id)
        except Exception as e:
            logger.warning("Code deployment failed for %s: %s", proposal.id, e)

    def approve(self, proposal_id: str) -> bool:
        """Manually approve a pending proposal (Yohan approval for major changes)."""
        cursor = self.conn.execute(
            "UPDATE code_proposals SET status = 'approved' WHERE id = ? AND status = 'pending_approval'",
            (proposal_id,),
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def reject(self, proposal_id: str) -> bool:
        """Manually reject a proposal."""
        now = datetime.now(timezone.utc).isoformat()
        cursor = self.conn.execute(
            "UPDATE code_proposals SET status = 'rejected', resolved_at = ? WHERE id = ? AND status IN ('proposed', 'pending_approval', 'testing')",
            (now, proposal_id),
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def mark_deployed(self, proposal_id: str) -> bool:
        """Mark an approved proposal as deployed.

        Sandbox gate check: detect/test/benchmark always run, but the actual
        deploy step is gated. If sandboxed, the proposal stays 'approved'
        but is not applied.
        """
        # ── Sandbox gate check (deploy only) ────────────────────
        if self._sandbox_gate is not None:
            proposal = self._get_by_id(proposal_id)
            description = f"Deploy code proposal: {proposal.title}" if proposal else f"Deploy proposal {proposal_id}"
            decision = self._sandbox_gate.check(
                system_id="code_deploy",
                action=f"deploy_code:{proposal_id}",
                description=description,
                context={"proposal_id": proposal_id, "scope": proposal.scope.value if proposal else "unknown"},
                agent_id=proposal.agent_id if proposal else "system",
                risk_level="high" if (proposal and proposal.scope.value == "major") else "medium",
            )
            if not decision.was_executed:
                logger.info("Code deploy sandboxed: %s (stays approved, not applied)", proposal_id)
                return False

        now = datetime.now(timezone.utc).isoformat()
        cursor = self.conn.execute(
            "UPDATE code_proposals SET status = 'deployed', resolved_at = ? WHERE id = ? AND status = 'approved'",
            (now, proposal_id),
        )
        self.conn.commit()
        if cursor.rowcount > 0:
            logger.info("Proposal deployed: %s", proposal_id)
            self._record_lesson(proposal_id, success=True)
            return True
        return False

    # ── Queries ────────────────────────────────────────────────

    def get_proposed(self, limit: int = 20) -> list[CodeProposal]:
        return self._query("status = 'proposed'", limit=limit)

    def get_pending_approval(self, limit: int = 20) -> list[CodeProposal]:
        return self._query("status = 'pending_approval'", limit=limit)

    def get_approved(self, limit: int = 20) -> list[CodeProposal]:
        return self._query("status = 'approved'", limit=limit)

    def get_deployed(self, limit: int = 20) -> list[CodeProposal]:
        return self._query("status = 'deployed'", limit=limit)

    def get_history(self, limit: int = 50) -> list[CodeProposal]:
        return self._query("1=1", limit=limit)

    def stats(self) -> dict[str, Any]:
        rows = self.conn.execute(
            "SELECT status, COUNT(*) as cnt FROM code_proposals GROUP BY status"
        ).fetchall()
        total = self.conn.execute("SELECT COUNT(*) as c FROM code_proposals").fetchone()
        deployed = self.conn.execute(
            "SELECT AVG(improvement_pct) as avg_imp FROM code_proposals WHERE status = 'deployed' AND improvement_pct IS NOT NULL"
        ).fetchone()
        return {
            "total_proposals": total["c"] if total else 0,
            "by_status": {r["status"]: r["cnt"] for r in rows},
            "avg_improvement_pct": round(deployed["avg_imp"] or 0, 2) if deployed else 0,
        }

    # ── Helpers ────────────────────────────────────────────────

    def _get_by_id(self, proposal_id: str) -> Optional[CodeProposal]:
        row = self.conn.execute(
            "SELECT * FROM code_proposals WHERE id = ?", (proposal_id,),
        ).fetchone()
        return self._row_to_proposal(row) if row else None

    _ALLOWED_WHERE_CLAUSES = frozenset({
        "1=1",
        "status = 'proposed'",
        "status = 'pending_approval'",
        "status = 'approved'",
        "status = 'deployed'",
    })

    def _query(self, where: str, params: Optional[list] = None,
               limit: int = 20) -> list[CodeProposal]:
        if where not in self._ALLOWED_WHERE_CLAUSES:
            raise ValueError(f"Disallowed WHERE clause: {where}")
        sql = f"SELECT * FROM code_proposals WHERE {where} ORDER BY created_at DESC LIMIT ?"
        all_params = (params or []) + [limit]
        rows = self.conn.execute(sql, all_params).fetchall()
        return [self._row_to_proposal(r) for r in rows]

    def _record_lesson(self, proposal_id: str, success: bool) -> None:
        if not self._experience_memory:
            return
        proposal = self._get_by_id(proposal_id)
        if not proposal:
            return
        try:
            exp_type = "success" if success else "failure"
            desc = proposal.description
            if proposal.test_result:
                desc += f"\nTest result: {proposal.test_result[:200]}"
            self._experience_memory.record_experience(
                experience_type=exp_type,
                domain="self_writing_code",
                title=f"Code proposal: {proposal.title}",
                description=desc,
                context={"file": proposal.file_path, "scope": proposal.scope.value},
            )
        except Exception as exc:
            logger.warning("Failed to record lesson: %s", exc)

    @staticmethod
    def _row_to_proposal(row: sqlite3.Row) -> CodeProposal:
        return CodeProposal(
            id=row["id"], title=row["title"], description=row["description"],
            file_path=row["file_path"], scope=ProposalScope(row["scope"]),
            status=ProposalStatus(row["status"]),
            inefficiency_detected=row["inefficiency_detected"] or "",
            proposed_change=row["proposed_change"] or "",
            test_result=row["test_result"],
            benchmark_before=row["benchmark_before"],
            benchmark_after=row["benchmark_after"],
            improvement_pct=row["improvement_pct"],
            agent_id=row["agent_id"] or "system",
            created_at=row["created_at"],
            resolved_at=row["resolved_at"],
        )
