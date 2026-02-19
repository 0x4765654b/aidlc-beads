"""BonoboAgent -- write guard agent wrapping FileGuard, GitGuard, BeadsGuard."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from orchestrator.agents.base import BaseAgent
from orchestrator.lib.context.dispatch import (
    DispatchMessage,
    CompletionMessage,
    build_completion,
)
from orchestrator.lib.bonobo import AuditLog, FileGuard, GitGuard, BeadsGuard

logger = logging.getLogger("agents.bonobo")

# Supported guard operations and which guard handles them
_GUARD_OPERATIONS = {
    # FileGuard operations
    "write_file": "file",
    "delete_file": "file",
    "validate_path": "file",
    # GitGuard operations
    "create_branch": "git",
    "checkout_branch": "git",
    "commit": "git",
    "merge": "git",
    "get_status": "git",
    "get_diff": "git",
    # BeadsGuard operations
    "create_issue": "beads",
    "update_issue": "beads",
    "close_issue": "beads",
    "add_dependency": "beads",
}


class BonoboAgent(BaseAgent):
    """Write guard agent that validates and executes privileged operations.

    Other agents invoke Bonobo as a tool. Bonobo validates the operation
    via the guard libraries (Unit 3) before executing.

    Expects dispatch.instructions to be a JSON string with:
        operation: str -- one of the supported guard operations
        agent: str -- the requesting agent's identity
        path: str -- (file ops) target file path
        content: str -- (write_file) file content to write
        overwrite: bool -- (write_file) whether to overwrite existing
        branch_name: str -- (git ops) branch name
        base: str -- (create_branch) base branch
        message: str -- (commit) commit message
        files: list[str] -- (commit) files to stage
        issue_id: str -- (commit / beads ops) Beads issue ID
        title: str -- (create_issue) issue title
        issue_type: str -- (create_issue) issue type
        priority: int -- (create_issue) priority
        source: str -- (merge) source branch
        target: str -- (merge) target branch
        Additional kwargs are forwarded to the underlying guard method.
    """

    agent_type = "Bonobo"
    agent_mail_identity = "Bonobo"

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._audit_log: AuditLog | None = None
        self._file_guard: FileGuard | None = None
        self._git_guard: GitGuard | None = None
        self._beads_guard: BeadsGuard | None = None

    def _ensure_guards(self, workspace_root: str, project_key: str) -> None:
        """Lazily initialise guards when we know the workspace root."""
        if self._audit_log is not None:
            return

        self._audit_log = AuditLog(
            mail_client=self._mail, project_key=project_key
        )
        root = Path(workspace_root) if workspace_root else None
        self._file_guard = FileGuard(self._audit_log, workspace_root=root)
        self._git_guard = GitGuard(self._audit_log, workspace_root=root)
        self._beads_guard = BeadsGuard(self._audit_log, workspace=workspace_root)

    async def _execute(self, dispatch: DispatchMessage) -> CompletionMessage:
        """Validate and execute a privileged write operation."""
        logger.info(
            "[Bonobo] Handling guard request for stage='%s'", dispatch.stage_name
        )

        # ------------------------------------------------------------------
        # 1. Parse the operation request
        # ------------------------------------------------------------------
        request = _parse_request(dispatch)
        if not request:
            return build_completion(
                stage_name=dispatch.stage_name,
                beads_issue_id=dispatch.beads_issue_id,
                output_artifacts=[],
                summary="No operation request found in dispatch instructions.",
                status="failed",
                error_detail="Missing or invalid JSON in dispatch.instructions",
            )

        operation = request.get("operation", "")
        requesting_agent = request.get("agent", "Unknown")

        if operation not in _GUARD_OPERATIONS:
            error_msg = (
                f"Unknown operation '{operation}'. "
                f"Supported: {sorted(_GUARD_OPERATIONS.keys())}"
            )
            logger.warning("[Bonobo] %s", error_msg)
            return build_completion(
                stage_name=dispatch.stage_name,
                beads_issue_id=dispatch.beads_issue_id,
                output_artifacts=[],
                summary=error_msg,
                status="failed",
                error_detail=error_msg,
            )

        guard_type = _GUARD_OPERATIONS[operation]

        # ------------------------------------------------------------------
        # 2. Initialise guards
        # ------------------------------------------------------------------
        self._ensure_guards(dispatch.workspace_root, dispatch.project_key)

        # ------------------------------------------------------------------
        # 3. Dispatch to the appropriate guard
        # ------------------------------------------------------------------
        try:
            if guard_type == "file":
                result = self._handle_file_op(operation, request, requesting_agent)
            elif guard_type == "git":
                result = self._handle_git_op(operation, request, requesting_agent)
            elif guard_type == "beads":
                result = self._handle_beads_op(
                    operation, request, requesting_agent,
                    workspace=dispatch.workspace_root or None,
                )
            else:
                result = {"error": f"Unknown guard type: {guard_type}"}
        except PermissionError as exc:
            logger.warning(
                "[Bonobo] Operation denied: %s.%s by %s -- %s",
                guard_type,
                operation,
                requesting_agent,
                exc,
            )
            return build_completion(
                stage_name=dispatch.stage_name,
                beads_issue_id=dispatch.beads_issue_id,
                output_artifacts=[],
                summary=f"Operation denied: {exc}",
                status="failed",
                error_detail=str(exc),
            )
        except (FileExistsError, FileNotFoundError) as exc:
            logger.warning("[Bonobo] File error: %s", exc)
            return build_completion(
                stage_name=dispatch.stage_name,
                beads_issue_id=dispatch.beads_issue_id,
                output_artifacts=[],
                summary=f"File error: {exc}",
                status="failed",
                error_detail=str(exc),
            )
        except Exception as exc:
            logger.error(
                "[Bonobo] Unexpected error in %s.%s: %s",
                guard_type,
                operation,
                exc,
                exc_info=True,
            )
            return build_completion(
                stage_name=dispatch.stage_name,
                beads_issue_id=dispatch.beads_issue_id,
                output_artifacts=[],
                summary=f"Guard error: {exc}",
                status="failed",
                error_detail=str(exc),
            )

        # ------------------------------------------------------------------
        # 4. Build successful completion
        # ------------------------------------------------------------------
        output_artifacts = result.get("output_artifacts", [])
        summary = result.get("summary", f"{guard_type}.{operation} completed")

        logger.info("[Bonobo] Operation succeeded: %s.%s", guard_type, operation)
        return build_completion(
            stage_name=dispatch.stage_name,
            beads_issue_id=dispatch.beads_issue_id,
            output_artifacts=output_artifacts,
            summary=summary,
            status="completed",
        )

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    def _handle_file_op(
        self, operation: str, request: dict, agent: str
    ) -> dict:
        """Execute a FileGuard operation."""
        assert self._file_guard is not None

        if operation == "write_file":
            path = Path(request.get("path", ""))
            content = request.get("content", "")
            overwrite = request.get("overwrite", False)
            written_path = self._file_guard.write_file(
                path, content, agent, overwrite=overwrite
            )
            return {
                "summary": f"File written: {written_path}",
                "output_artifacts": [str(written_path)],
            }

        elif operation == "delete_file":
            path = Path(request.get("path", ""))
            self._file_guard.delete_file(path, agent)
            return {"summary": f"File deleted: {path}"}

        elif operation == "validate_path":
            path = Path(request.get("path", ""))
            op_type = request.get("op_type", "write")
            result = self._file_guard.validate_path(path, op_type)
            return {
                "summary": (
                    f"Path validation: {'allowed' if result.allowed else 'denied'} "
                    f"-- {result.reason}"
                ),
            }

        return {"summary": f"Unknown file operation: {operation}"}

    # ------------------------------------------------------------------
    # Git operations
    # ------------------------------------------------------------------

    def _handle_git_op(
        self, operation: str, request: dict, agent: str
    ) -> dict:
        """Execute a GitGuard operation."""
        assert self._git_guard is not None

        if operation == "create_branch":
            branch_name = request.get("branch_name", "")
            base = request.get("base", "main")
            created = self._git_guard.create_branch(branch_name, agent, base)
            return {"summary": f"Branch created: {created}"}

        elif operation == "checkout_branch":
            branch_name = request.get("branch_name", "")
            self._git_guard.checkout_branch(branch_name, agent)
            return {"summary": f"Switched to branch: {branch_name}"}

        elif operation == "commit":
            message = request.get("message", "")
            files = [Path(f) for f in request.get("files", [])]
            issue_id = request.get("issue_id", "")
            commit_hash = self._git_guard.commit(message, files, agent, issue_id)
            return {"summary": f"Committed: {commit_hash[:12]}"}

        elif operation == "merge":
            source = request.get("source", "")
            target = request.get("target", "")
            strategy = request.get("strategy", "merge")
            merge_result = self._git_guard.merge(source, target, agent, strategy)
            if merge_result.success:
                return {
                    "summary": f"Merge successful: {merge_result.commit_hash or ''}",
                }
            else:
                return {
                    "summary": (
                        f"Merge failed with conflicts: {merge_result.conflicts}"
                    ),
                }

        elif operation == "get_status":
            status = self._git_guard.get_status()
            return {
                "summary": (
                    f"Branch: {status.branch}, clean: {status.clean}, "
                    f"staged: {len(status.staged)}, modified: {len(status.modified)}, "
                    f"untracked: {len(status.untracked)}"
                ),
            }

        elif operation == "get_diff":
            path = Path(request["path"]) if request.get("path") else None
            diff = self._git_guard.get_diff(path)
            return {"summary": f"Diff output ({len(diff)} chars)"}

        return {"summary": f"Unknown git operation: {operation}"}

    # ------------------------------------------------------------------
    # Beads operations
    # ------------------------------------------------------------------

    def _handle_beads_op(
        self, operation: str, request: dict, agent: str, workspace: str | None = None
    ) -> dict:
        """Execute a BeadsGuard operation."""
        assert self._beads_guard is not None

        if operation == "create_issue":
            title = request.get("title", "")
            issue_type = request.get("issue_type", "task")
            priority = int(request.get("priority", 2))
            # Forward extra kwargs
            extra = {}
            for key in ("description", "labels", "assignee", "notes", "acceptance", "thread"):
                if key in request:
                    extra[key] = request[key]
            issue = self._beads_guard.guarded_create(
                title, issue_type, priority, agent, **extra
            )
            return {
                "summary": f"Issue created: {issue.id} -- {issue.title}",
                "output_artifacts": [issue.id],
            }

        elif operation == "update_issue":
            issue_id = request.get("issue_id", "")
            changes = {
                k: v
                for k, v in request.items()
                if k not in ("operation", "agent", "issue_id")
            }
            self._beads_guard.guarded_update(issue_id, agent, **changes)
            return {"summary": f"Issue updated: {issue_id}"}

        elif operation == "close_issue":
            issue_id = request.get("issue_id", "")
            reason = request.get("reason")
            self._beads_guard.guarded_close(issue_id, agent, reason)
            return {"summary": f"Issue closed: {issue_id}"}

        elif operation == "add_dependency":
            blocked_id = request.get("blocked_id", "")
            blocker_id = request.get("blocker_id", "")
            dep_type = request.get("dep_type", "blocks")
            validation = self._beads_guard.validate_dependency(
                blocked_id, blocker_id, dep_type, agent
            )
            if not validation.allowed:
                raise PermissionError(
                    f"BeadsGuard denied dependency: {validation.reason}"
                )
            from orchestrator.lib.beads.client import add_dependency

            add_dependency(blocked_id, blocker_id, dep_type, workspace=workspace)
            return {
                "summary": (
                    f"Dependency added: {blocker_id} blocks {blocked_id}"
                ),
            }

        return {"summary": f"Unknown beads operation: {operation}"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_request(dispatch: DispatchMessage) -> dict | None:
    """Parse the operation request from dispatch instructions."""
    if not dispatch.instructions:
        return None
    try:
        data = json.loads(dispatch.instructions)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, TypeError):
        pass
    logger.warning("[Bonobo] Could not parse instructions as JSON")
    return None
