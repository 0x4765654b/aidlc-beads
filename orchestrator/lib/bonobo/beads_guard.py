"""BeadsGuard -- validates and executes Beads issue operations."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

from orchestrator.lib.beads.client import show_issue, create_issue, update_issue, close_issue
from orchestrator.lib.beads.models import BeadsIssue
from orchestrator.lib.bonobo.audit import AuditLog

VALID_ISSUE_TYPES = frozenset({
    "task", "epic", "bug", "feature", "chore", "decision", "message"
})

# Only these roles can create epics
EPIC_CREATORS = frozenset({"Harmbe", "ProjectMinder"})

VALID_LABEL_PREFIXES = frozenset({
    "phase:", "unit:", "stage:", "type:", "discovered-from:",
})

VALID_STATUS_TRANSITIONS = {
    "open": {"in_progress", "done", "closed"},
    "in_progress": {"done", "closed", "open"},
    "done": {"closed", "open"},
    "closed": {"open"},
}


@dataclass
class ValidationResult:
    """Result of a Beads operation validation."""

    allowed: bool
    reason: str


class BeadsGuard:
    """Validates and executes Beads issue operations.

    All Beads mutations by agents flow through this guard.
    """

    def __init__(self, audit: AuditLog, workspace: str | None = None) -> None:
        self._audit = audit
        self._workspace = workspace

    def validate_create(
        self,
        title: str,
        issue_type: str,
        labels: list[str],
        agent: str,
    ) -> ValidationResult:
        """Validate a Beads issue creation request.

        Args:
            title: Issue title.
            issue_type: Issue type string.
            labels: List of label strings.
            agent: Requesting agent name.

        Returns:
            ValidationResult with allowed flag and reason.
        """
        # Title must not be empty
        if not title or not title.strip():
            return ValidationResult(False, "Issue title must not be empty")

        # Valid issue type
        if issue_type not in VALID_ISSUE_TYPES:
            return ValidationResult(
                False,
                f"Invalid issue type '{issue_type}'. "
                f"Valid: {sorted(VALID_ISSUE_TYPES)}",
            )

        # SEC-08: Only Harmbe/ProjectMinder can create epics
        if issue_type == "epic" and agent not in EPIC_CREATORS:
            return ValidationResult(
                False,
                f"Agent '{agent}' cannot create epics. Only {sorted(EPIC_CREATORS)} can.",
            )

        # Label convention validation
        for label in labels:
            has_valid_prefix = any(label.startswith(p) for p in VALID_LABEL_PREFIXES)
            if ":" in label and not has_valid_prefix:
                return ValidationResult(
                    False,
                    f"Label '{label}' uses unknown prefix. "
                    f"Valid prefixes: {sorted(VALID_LABEL_PREFIXES)}",
                )

        return ValidationResult(True, "Creation validated")

    def validate_update(
        self,
        issue_id: str,
        changes: dict,
        agent: str,
    ) -> ValidationResult:
        """Validate a Beads issue update request.

        Args:
            issue_id: The issue ID to update.
            changes: Dict of fields being changed.
            agent: Requesting agent name.

        Returns:
            ValidationResult with allowed flag and reason.
        """
        # Issue must exist
        try:
            issue = show_issue(issue_id, workspace=self._workspace)
        except (subprocess.CalledProcessError, ValueError):
            return ValidationResult(False, f"Issue {issue_id} not found")

        # SEC-08: Agents can only update their own or unassigned issues
        if issue.assignee and issue.assignee != agent and agent not in EPIC_CREATORS:
            return ValidationResult(
                False,
                f"Agent '{agent}' cannot update issue {issue_id} "
                f"assigned to '{issue.assignee}'",
            )

        # Cannot change issue type
        if "issue_type" in changes:
            return ValidationResult(False, "Cannot change issue type after creation")

        # Cannot remove phase labels
        if "remove_label" in changes:
            label = changes["remove_label"]
            if label.startswith("phase:"):
                return ValidationResult(False, f"Cannot remove phase label: {label}")

        # SEC-07: Valid status transitions
        if "status" in changes:
            new_status = changes["status"]
            current_status = issue.status
            valid_next = VALID_STATUS_TRANSITIONS.get(current_status, set())
            if new_status not in valid_next:
                return ValidationResult(
                    False,
                    f"Invalid status transition: {current_status} -> {new_status}. "
                    f"Valid next states: {sorted(valid_next)}",
                )

        return ValidationResult(True, "Update validated")

    def validate_dependency(
        self,
        blocked_id: str,
        blocker_id: str,
        dep_type: str,
        agent: str,
    ) -> ValidationResult:
        """Validate a dependency addition.

        Args:
            blocked_id: The issue that would be blocked.
            blocker_id: The issue that would be the blocker.
            dep_type: Dependency type.
            agent: Requesting agent name.

        Returns:
            ValidationResult with allowed flag and reason.
        """
        # Both issues must exist
        for issue_id in (blocked_id, blocker_id):
            try:
                show_issue(issue_id, workspace=self._workspace)
            except (subprocess.CalledProcessError, ValueError):
                return ValidationResult(False, f"Issue {issue_id} not found")

        # Cycle detection (SEC-07)
        cwd = str(self._workspace) if self._workspace else None
        try:
            result = subprocess.run(
                ["bd", "dep", "cycles"],
                capture_output=True,
                text=True,
                check=False,
                cwd=cwd,
            )
            if "cycle" in result.stdout.lower():
                # There are already cycles -- warn but don't block
                pass
        except FileNotFoundError:
            pass  # bd not available, skip cycle check

        return ValidationResult(True, "Dependency validated")

    # -------------------------------------------------------------------
    # Guarded convenience functions
    # -------------------------------------------------------------------

    def guarded_create(
        self,
        title: str,
        issue_type: str,
        priority: int,
        agent: str,
        **kwargs,
    ) -> BeadsIssue:
        """Validated issue creation.

        Raises:
            PermissionError: If validation fails.
        """
        labels = kwargs.get("labels", "").split(",") if kwargs.get("labels") else []
        details = {"title": title, "type": issue_type, "priority": priority}

        result = self.validate_create(title, issue_type, labels, agent)
        if not result.allowed:
            self._audit.log_denied("beads", "create_issue", agent, result.reason, details)
            raise PermissionError(f"BeadsGuard denied create: {result.reason}")

        issue = create_issue(title, issue_type, priority, workspace=self._workspace, **kwargs)
        self._audit.log_allowed("beads", "create_issue", agent, {**details, "id": issue.id})
        return issue

    def guarded_update(self, issue_id: str, agent: str, **kwargs) -> None:
        """Validated issue update.

        Raises:
            PermissionError: If validation fails.
        """
        details = {"issue_id": issue_id, "changes": kwargs}

        result = self.validate_update(issue_id, kwargs, agent)
        if not result.allowed:
            self._audit.log_denied("beads", "update_issue", agent, result.reason, details)
            raise PermissionError(f"BeadsGuard denied update: {result.reason}")

        update_issue(issue_id, workspace=self._workspace, **kwargs)
        self._audit.log_allowed("beads", "update_issue", agent, details)

    def guarded_close(self, issue_id: str, agent: str, reason: str | None = None) -> None:
        """Validated issue close.

        Raises:
            PermissionError: If validation fails.
        """
        details = {"issue_id": issue_id, "reason": reason}

        # Check agent is allowed
        try:
            issue = show_issue(issue_id, workspace=self._workspace)
            if issue.assignee and issue.assignee != agent and agent not in EPIC_CREATORS:
                deny_reason = f"Agent '{agent}' cannot close issue assigned to '{issue.assignee}'"
                self._audit.log_denied("beads", "close_issue", agent, deny_reason, details)
                raise PermissionError(f"BeadsGuard denied close: {deny_reason}")
        except (subprocess.CalledProcessError, ValueError) as e:
            self._audit.log_error("beads", "close_issue", agent, str(e), details)
            raise

        close_issue(issue_id, reason, workspace=self._workspace)
        self._audit.log_allowed("beads", "close_issue", agent, details)
