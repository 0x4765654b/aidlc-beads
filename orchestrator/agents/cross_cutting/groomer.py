"""Groomer -- event monitor and notification router."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from orchestrator.agents.base import BaseAgent
from orchestrator.lib.context.dispatch import (
    DispatchMessage,
    CompletionMessage,
    build_completion,
)
from orchestrator.lib.beads.client import list_issues, show_issue

logger = logging.getLogger("agents.groomer")

# Issues in "in_progress" status older than this many hours are flagged stale
STALE_THRESHOLD_HOURS = 48

# Review gates open longer than this are flagged overdue
OVERDUE_REVIEW_HOURS = 24


class Groomer(BaseAgent):
    """Event-driven agent that monitors Agent Mail for state changes.

    Responsibilities:
    - Session resume: compile status report from accumulated inbox
    - Route state-change notifications to Project Minder or Harmbe
    - Detect stale state (stuck issues, overdue reviews)
    - Track discovered work and flag to Project Minder
    """

    agent_type = "Groomer"
    agent_mail_identity = "Groomer"

    async def _execute(self, dispatch: DispatchMessage) -> CompletionMessage:
        """Monitor project state and compile a status report.

        This agent does not require LLM calls -- it performs deterministic
        checks against Agent Mail and Beads state.
        """
        logger.info(
            "[Groomer] Starting monitoring cycle for project='%s'",
            dispatch.project_key,
        )

        report_sections: list[str] = []
        discovered_issues: list[dict] = []

        # ------------------------------------------------------------------
        # 1. Check Agent Mail inbox for notifications
        # ------------------------------------------------------------------
        inbox_summary = await self._check_inbox(dispatch)
        if inbox_summary:
            report_sections.append(inbox_summary)

        # ------------------------------------------------------------------
        # 2. Query Beads for stale issues
        # ------------------------------------------------------------------
        stale_summary, stale_discovered = await self._check_stale_issues()
        if stale_summary:
            report_sections.append(stale_summary)
        discovered_issues.extend(stale_discovered)

        # ------------------------------------------------------------------
        # 3. Detect overdue review gates
        # ------------------------------------------------------------------
        overdue_summary, overdue_discovered = await self._check_overdue_reviews()
        if overdue_summary:
            report_sections.append(overdue_summary)
        discovered_issues.extend(overdue_discovered)

        # ------------------------------------------------------------------
        # 4. Compile the session status report
        # ------------------------------------------------------------------
        if not report_sections:
            report_sections.append("No notable events or issues detected.")

        full_report = "# Groomer Monitoring Report\n\n" + "\n\n".join(
            report_sections
        )
        logger.info(
            "[Groomer] Report compiled (%d sections, %d discovered issues)",
            len(report_sections),
            len(discovered_issues),
        )

        # ------------------------------------------------------------------
        # 5. Send report to Harmbe via Agent Mail
        # ------------------------------------------------------------------
        await self._send_report_to_harmbe(dispatch, full_report, discovered_issues)

        return build_completion(
            stage_name=dispatch.stage_name,
            beads_issue_id=dispatch.beads_issue_id,
            output_artifacts=[],
            summary=full_report[:500],
            status="completed",
            discovered_issues=discovered_issues,
        )

    # ------------------------------------------------------------------
    # Inbox check
    # ------------------------------------------------------------------

    async def _check_inbox(self, dispatch: DispatchMessage) -> str:
        """Fetch and summarise Agent Mail inbox messages."""
        if not self._mail:
            logger.info("[Groomer] No mail client -- skipping inbox check")
            return ""

        try:
            messages = self._mail.fetch_inbox(
                dispatch.project_key,
                self.agent_mail_identity,
                limit=50,
                unread_only=True,
            )
        except Exception as exc:
            logger.warning("[Groomer] Failed to fetch inbox: %s", exc)
            return f"## Inbox\nFailed to fetch inbox: {exc}"

        if not messages:
            return "## Inbox\nNo unread messages."

        lines = [f"## Inbox ({len(messages)} unread messages)\n"]
        error_count = 0
        state_change_count = 0
        other_count = 0

        for msg in messages:
            prefix = ""
            subject = msg.subject or "(no subject)"
            if "[ERROR]" in subject or "[ESCALATION]" in subject:
                error_count += 1
                prefix = "!!!"
            elif "state" in subject.lower() or "status" in subject.lower():
                state_change_count += 1
                prefix = "-->"
            else:
                other_count += 1
                prefix = "   "

            lines.append(
                f"- {prefix} **{msg.from_agent}**: {subject}"
            )

            # Acknowledge the message
            try:
                if msg.id:
                    self._mail.acknowledge_message(
                        dispatch.project_key, self.agent_mail_identity, msg.id
                    )
            except Exception:
                pass  # Best-effort acknowledgement

        lines.append(
            f"\nSummary: {error_count} errors/escalations, "
            f"{state_change_count} state changes, {other_count} other."
        )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Stale issue detection
    # ------------------------------------------------------------------

    async def _check_stale_issues(self) -> tuple[str, list[dict]]:
        """Query Beads for issues stuck in 'in_progress' too long."""
        discovered: list[dict] = []
        try:
            in_progress = list_issues(status="in_progress")
        except Exception as exc:
            logger.warning("[Groomer] Failed to list in-progress issues: %s", exc)
            return f"## Stale Issues\nFailed to query Beads: {exc}", []

        if not in_progress:
            return "## Stale Issues\nNo in-progress issues found.", []

        now = datetime.now(timezone.utc)
        stale: list[str] = []

        for issue in in_progress:
            age_hours = _issue_age_hours(issue, now)
            if age_hours is not None and age_hours > STALE_THRESHOLD_HOURS:
                stale.append(
                    f"- **{issue.id}** ({issue.title}): "
                    f"in_progress for {age_hours:.0f}h "
                    f"(threshold: {STALE_THRESHOLD_HOURS}h)"
                )
                discovered.append({
                    "type": "stale_issue",
                    "issue_id": issue.id,
                    "title": issue.title,
                    "age_hours": age_hours,
                })

        if not stale:
            return (
                f"## Stale Issues\n{len(in_progress)} in-progress issues, none stale.",
                [],
            )

        header = f"## Stale Issues ({len(stale)} detected)\n"
        return header + "\n".join(stale), discovered

    # ------------------------------------------------------------------
    # Overdue review detection
    # ------------------------------------------------------------------

    async def _check_overdue_reviews(self) -> tuple[str, list[dict]]:
        """Look for open review gate issues older than the threshold."""
        discovered: list[dict] = []
        try:
            review_issues = list_issues(label="stage:review-gate", status="open")
        except Exception as exc:
            logger.warning(
                "[Groomer] Failed to list review-gate issues: %s", exc
            )
            return f"## Overdue Reviews\nFailed to query Beads: {exc}", []

        if not review_issues:
            return "## Overdue Reviews\nNo open review gates found.", []

        now = datetime.now(timezone.utc)
        overdue: list[str] = []

        for issue in review_issues:
            age_hours = _issue_age_hours(issue, now)
            if age_hours is not None and age_hours > OVERDUE_REVIEW_HOURS:
                overdue.append(
                    f"- **{issue.id}** ({issue.title}): "
                    f"open for {age_hours:.0f}h "
                    f"(threshold: {OVERDUE_REVIEW_HOURS}h)"
                )
                discovered.append({
                    "type": "overdue_review",
                    "issue_id": issue.id,
                    "title": issue.title,
                    "age_hours": age_hours,
                })

        if not overdue:
            return (
                f"## Overdue Reviews\n{len(review_issues)} open review gates, none overdue.",
                [],
            )

        header = f"## Overdue Reviews ({len(overdue)} detected)\n"
        return header + "\n".join(overdue), discovered

    # ------------------------------------------------------------------
    # Report delivery
    # ------------------------------------------------------------------

    async def _send_report_to_harmbe(
        self,
        dispatch: DispatchMessage,
        report: str,
        discovered_issues: list[dict],
    ) -> None:
        """Send the compiled status report to Harmbe via Agent Mail."""
        if not self._mail:
            logger.info("[Groomer] No mail client -- report not sent")
            return

        importance = "normal"
        if discovered_issues:
            importance = "high"

        subject = "[STATUS] Groomer monitoring report"
        if discovered_issues:
            subject += f" ({len(discovered_issues)} items flagged)"

        try:
            self._mail.send_message(
                dispatch.project_key,
                self.agent_mail_identity,
                ["Harmbe"],
                subject,
                report,
                thread_id="groomer-monitoring",
                importance=importance,
            )
            logger.info("[Groomer] Status report sent to Harmbe")
        except Exception as exc:
            logger.warning(
                "[Groomer] Failed to send report to Harmbe: %s", exc
            )


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _issue_age_hours(issue, now: datetime) -> float | None:
    """Calculate how many hours ago an issue was last updated (or created).

    Returns None if timestamps cannot be parsed.
    """
    timestamp_str = issue.updated_at or issue.created_at
    if not timestamp_str:
        return None

    try:
        # Try ISO 8601 format
        ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        delta = now - ts
        return delta.total_seconds() / 3600.0
    except (ValueError, TypeError):
        logger.debug(
            "[Groomer] Could not parse timestamp '%s' for issue %s",
            timestamp_str,
            issue.id,
        )
        return None
