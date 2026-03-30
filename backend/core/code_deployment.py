"""
Code Deployment Pipeline — test-deploy-monitor-rollback for self-writing code.

When an engineering agent proposes a code change, this pipeline:
1. Writes the proposed content to the target file
2. Runs the test suite via pytest
3. Keeps the change on success, rolls back on failure

Every deployment is recorded so ROOT can track success rates and learn
which kinds of code proposals tend to pass tests.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from backend.config import ROOT_DIR

logger = logging.getLogger("root.code_deployment")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Data ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class DeploymentResult:
    """Immutable record of a deployment attempt."""

    proposal_id: str
    success: bool
    tests_passed: bool
    test_output: str
    file_path: str
    deployed_at: str = ""
    rolled_back: bool = False
    error: str = ""


# ── Pipeline ──────────────────────────────────────────────────


class CodeDeploymentPipeline:
    """Test-deploy-monitor-rollback pipeline for self-writing code proposals.

    Writes proposed content, runs pytest, and either keeps the change
    or rolls back automatically.
    """

    def __init__(self, project_root: Optional[Path] = None) -> None:
        self._project_root = project_root or ROOT_DIR
        self._history: list[DeploymentResult] = []
        self._deploy_count = 0
        self._success_count = 0
        self._rollback_count = 0
        logger.info(
            "CodeDeploymentPipeline initialised (root=%s)", self._project_root,
        )

    # ── Core API ──────────────────────────────────────────────

    async def deploy_proposal(
        self,
        file_path: str,
        original_content: str,
        proposed_content: str,
        proposal_id: str,
    ) -> DeploymentResult:
        """Deploy a code proposal: write, test, keep or rollback.

        Args:
            file_path: Absolute or project-relative path to the target file.
            original_content: Content to restore on rollback.
            proposed_content: The new code to deploy.
            proposal_id: Unique identifier for this proposal.

        Returns:
            DeploymentResult capturing outcome details.
        """
        self._deploy_count += 1
        target = Path(file_path)
        if not target.is_absolute():
            target = self._project_root / target

        # ── Step 1: Write proposed content ────────────────────
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(proposed_content, encoding="utf-8")
            logger.info("Wrote proposed content to %s (proposal=%s)", target, proposal_id)
        except Exception as exc:
            logger.error("Failed to write proposal %s: %s", proposal_id, exc)
            return self._record(DeploymentResult(
                proposal_id=proposal_id,
                success=False,
                tests_passed=False,
                test_output="",
                file_path=str(target),
                error=f"Write failed: {exc}",
            ))

        # ── Step 2: Run pytest ────────────────────────────────
        tests_passed = False
        test_output = ""
        try:
            proc = await asyncio.create_subprocess_exec(
                "python", "-m", "pytest", "tests/", "-x", "-q", "--timeout=60",
                cwd=str(self._project_root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            stdout_bytes, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
            test_output = (stdout_bytes or b"").decode("utf-8", errors="replace")
            tests_passed = proc.returncode == 0
        except asyncio.TimeoutError:
            test_output = "pytest timed out after 120 seconds"
            logger.warning("Tests timed out for proposal %s", proposal_id)
        except Exception as exc:
            test_output = f"pytest execution error: {exc}"
            logger.error("Test execution failed for proposal %s: %s", proposal_id, exc)

        # ── Step 3: Keep or rollback ──────────────────────────
        if tests_passed:
            self._success_count += 1
            logger.info("Tests PASSED for proposal %s — keeping change", proposal_id)
            return self._record(DeploymentResult(
                proposal_id=proposal_id,
                success=True,
                tests_passed=True,
                test_output=test_output,
                file_path=str(target),
                deployed_at=_now_iso(),
            ))
        else:
            logger.warning("Tests FAILED for proposal %s — rolling back", proposal_id)
            await self.rollback(str(target), original_content)
            self._rollback_count += 1
            return self._record(DeploymentResult(
                proposal_id=proposal_id,
                success=False,
                tests_passed=False,
                test_output=test_output,
                file_path=str(target),
                rolled_back=True,
                error="Tests failed; rolled back to original content",
            ))

    async def rollback(self, file_path: str, original_content: str) -> None:
        """Restore a file to its original content."""
        target = Path(file_path)
        try:
            target.write_text(original_content, encoding="utf-8")
            logger.info("Rolled back %s to original content", target)
        except Exception as exc:
            logger.error("CRITICAL: Rollback failed for %s: %s", target, exc)

    # ── Internal ──────────────────────────────────────────────

    def _record(self, result: DeploymentResult) -> DeploymentResult:
        """Store a result in history and return it."""
        self._history.append(result)
        return result

    def stats(self) -> dict[str, Any]:
        """Return runtime statistics."""
        return {
            "total_deployments": self._deploy_count,
            "successful": self._success_count,
            "rolled_back": self._rollback_count,
            "failed_other": self._deploy_count - self._success_count - self._rollback_count,
            "success_rate": (
                self._success_count / self._deploy_count
                if self._deploy_count > 0
                else 0.0
            ),
            "history_length": len(self._history),
            "project_root": str(self._project_root),
        }
