"""Review gate handler — hybrid rules + LLM evaluation."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from rafiki.models import ReviewDecisionRecord

logger = logging.getLogger("rafiki.handlers.review")

# Expected headings per stage type (stage keyword → required heading fragments)
STAGE_HEADINGS: dict[str, list[str]] = {
    "requirements": ["requirements", "scope", "stakeholder"],
    "functional": ["api", "specification", "design"],
    "architecture": ["architecture", "component", "deployment"],
    "nfr": ["performance", "security", "reliability"],
    "infrastructure": ["infrastructure", "deployment", "monitoring"],
    "user-stories": ["user stor", "acceptance criteria"],
    "reverse-engineering": ["architecture", "component", "dependencies"],
}

PLACEHOLDER_PATTERNS = [
    re.compile(r"^#+\s+.*\bTODO\b", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^#+\s+.*\bTBD\b", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^#+\s+.*\bFIXME\b", re.MULTILINE | re.IGNORECASE),
]


@dataclass
class StructuralCheckResult:
    passed: bool = True
    failures: list[str] = field(default_factory=list)
    checks_run: int = 0
    checks_passed: int = 0


class ReviewHandler:
    """Evaluates review gates using structural checks and optional LLM."""

    def __init__(
        self,
        review_client,  # ReviewClient
        issue_filer,    # IssueFiler
        *,
        auto_approve: bool = False,
        llm_enabled: bool = True,
        vision_text: str = "",
        tech_env_text: str = "",
    ):
        self.review_client = review_client
        self.issue_filer = issue_filer
        self.auto_approve = auto_approve
        self.llm_enabled = llm_enabled
        self.vision_text = vision_text
        self.tech_env_text = tech_env_text

    async def handle(self, review: dict) -> ReviewDecisionRecord:
        """Evaluate a review gate and approve or reject it."""
        issue_id = review.get("issue_id", "")
        title = review.get("title", "")
        artifact_content = review.get("artifact_content", "") or ""
        stage_name = review.get("stage_name", "") or self._infer_stage(title)

        # Layer 3 — Auto-approve
        if self.auto_approve:
            logger.info("Auto-approving review %s", issue_id)
            await self.review_client.approve(issue_id, feedback="Auto-approved by Rafiki")
            return ReviewDecisionRecord(
                issue_id=issue_id, decision="approved",
                feedback="Auto-approved by Rafiki", strategy="auto_approve",
            )

        # Layer 1 — Structural checks
        structural = self._structural_checks(artifact_content, stage_name)

        if not structural.passed:
            feedback = "Structural checks failed:\n" + "\n".join(f"- {f}" for f in structural.failures)
            logger.warning("Rejecting review %s: %s", issue_id, feedback)
            await self.review_client.reject(issue_id, feedback=feedback)
            # File a bug
            await self.issue_filer.file_bug(
                f"Rafiki: {structural.failures[0]}",
                f"Review gate {issue_id} ({title}) failed structural checks.\n\n"
                + "\n".join(f"- {f}" for f in structural.failures),
                priority=1,
                source=f"review-{stage_name}",
            )
            return ReviewDecisionRecord(
                issue_id=issue_id, decision="rejected",
                feedback=feedback, strategy="rules",
            )

        # Layer 2 — LLM evaluation (stubbed — real impl would call Bedrock)
        if self.llm_enabled:
            llm_result = await self._llm_evaluate(artifact_content, stage_name)
            if llm_result["decision"] == "REJECT":
                feedback = llm_result.get("rationale", "LLM rejected the artifact")
                await self.review_client.reject(issue_id, feedback=feedback)
                await self.issue_filer.file_bug(
                    f"Rafiki: LLM rejected {stage_name} artifact",
                    f"Review gate {issue_id} ({title}) — LLM evaluation:\n{feedback}",
                    priority=1,
                    source=f"review-{stage_name}",
                )
                return ReviewDecisionRecord(
                    issue_id=issue_id, decision="rejected",
                    feedback=feedback, strategy="llm",
                )
            feedback = llm_result.get("rationale", "Approved by LLM evaluation")
            strategy = "llm"
        else:
            feedback = f"Structural checks passed ({structural.checks_passed}/{structural.checks_run})"
            strategy = "rules"

        logger.info("Approving review %s (strategy=%s)", issue_id, strategy)
        await self.review_client.approve(issue_id, feedback=feedback)
        return ReviewDecisionRecord(
            issue_id=issue_id, decision="approved",
            feedback=feedback, strategy=strategy,
        )

    def _structural_checks(self, content: str, stage_name: str) -> StructuralCheckResult:
        """Run rule-based structural checks on artifact content."""
        result = StructuralCheckResult()

        # Check 1: Non-empty
        result.checks_run += 1
        if not content or not content.strip():
            result.passed = False
            result.failures.append("Artifact content is empty")
            return result
        result.checks_passed += 1

        # Check 2: Minimum length
        result.checks_run += 1
        if len(content.strip()) < 200:
            result.passed = False
            result.failures.append(f"Artifact is too short ({len(content.strip())} chars, minimum 200)")
        else:
            result.checks_passed += 1

        # Check 3: Expected headings for stage type
        result.checks_run += 1
        stage_key = self._match_stage_key(stage_name)
        if stage_key and stage_key in STAGE_HEADINGS:
            content_lower = content.lower()
            missing = [h for h in STAGE_HEADINGS[stage_key] if h not in content_lower]
            if len(missing) == len(STAGE_HEADINGS[stage_key]):
                result.passed = False
                result.failures.append(f"Missing expected content for {stage_key} stage")
            else:
                result.checks_passed += 1
        else:
            result.checks_passed += 1  # No specific headings to check

        # Check 4: No placeholder text in headings
        result.checks_run += 1
        placeholders_found = []
        for pattern in PLACEHOLDER_PATTERNS:
            matches = pattern.findall(content)
            placeholders_found.extend(matches)
        if placeholders_found:
            result.passed = False
            result.failures.append(f"Placeholder text in headings: {', '.join(placeholders_found[:3])}")
        else:
            result.checks_passed += 1

        return result

    @staticmethod
    def _match_stage_key(stage_name: str) -> str:
        """Match a stage name to a key in STAGE_HEADINGS."""
        stage_lower = stage_name.lower()
        for key in STAGE_HEADINGS:
            if key in stage_lower:
                return key
        return ""

    @staticmethod
    def _infer_stage(title: str) -> str:
        """Infer stage name from review gate title."""
        # Titles are like "REVIEW: Workspace Detection - Awaiting Approval"
        title = title.replace("REVIEW:", "").replace("- Awaiting Approval", "").strip()
        return title

    async def _llm_evaluate(self, content: str, stage_name: str) -> dict:
        """Evaluate artifact quality via LLM. Returns dict with 'decision' and 'rationale'."""
        # Stub implementation — in production, this calls Bedrock
        # For now, approve if structural checks passed
        logger.info("LLM evaluation for %s (stub: auto-approve)", stage_name)
        return {
            "decision": "APPROVE",
            "rationale": f"Artifact for {stage_name} passes structural validation (LLM stub)",
        }
