"""Python wrapper around the Beads (bd) CLI.

All functions shell out to `bd` and parse JSON output.
No LLM dependency -- pure subprocess calls.

Every public function accepts an optional ``workspace`` keyword argument.
When provided, it is passed as ``cwd`` to ``subprocess.run`` so that
``bd`` discovers the correct per-project ``.beads/`` directory.
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Any

from orchestrator.lib.beads.models import BeadsIssue

logger = logging.getLogger("lib.beads.client")


def _run_bd(
    *args: str,
    json_output: bool = False,
    workspace: str | Path | None = None,
) -> str | Any:
    """Run a bd CLI command and return output.

    Args:
        *args: CLI arguments after 'bd'.
        json_output: If True, append --json and parse the result.
        workspace: Working directory for the bd process.  When set,
            ``bd`` will discover the ``.beads/`` database relative to
            this path instead of relying on the ``BEADS_DIR`` env var.

    Returns:
        Parsed JSON (dict or list) if json_output, else raw stdout string.

    Raises:
        RuntimeError: If bd is not found on PATH.
        subprocess.CalledProcessError: If bd exits non-zero.
        ValueError: If JSON parsing fails.
    """
    cmd = ["bd", *args]
    if json_output:
        cmd.append("--json")

    cwd = str(workspace) if workspace else None

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            cwd=cwd,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "Beads CLI (bd) not found on PATH. "
            "Install Beads: https://github.com/steveyegge/beads"
        ) from None

    stdout = result.stdout.strip()

    if json_output:
        if not stdout:
            return {}
        try:
            return json.loads(stdout)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse bd JSON output: {e}\nOutput: {stdout[:500]}") from e

    return stdout


def _parse_issue(data: dict) -> BeadsIssue:
    """Parse a single issue from bd JSON output."""
    return BeadsIssue.from_json(data)


def _parse_issues(data: Any) -> list[BeadsIssue]:
    """Parse a list of issues from bd JSON output."""
    if isinstance(data, list):
        return [_parse_issue(item) for item in data]
    if isinstance(data, dict):
        # Some bd commands return {"issues": [...]}
        issues = data.get("issues", data.get("items", []))
        if isinstance(issues, list):
            return [_parse_issue(item) for item in issues]
        return [_parse_issue(data)]
    return []


# ---------------------------------------------------------------------------
# Issue CRUD
# ---------------------------------------------------------------------------


def create_issue(
    title: str,
    issue_type: str = "task",
    priority: int = 2,
    *,
    description: str | None = None,
    labels: str | None = None,
    assignee: str | None = None,
    notes: str | None = None,
    acceptance: str | None = None,
    thread: str | None = None,
    workspace: str | Path | None = None,
) -> BeadsIssue:
    """Create a Beads issue.

    Returns:
        The created BeadsIssue.
    """
    args = ["create", title, "-t", issue_type, "-p", str(priority)]
    if description:
        args.extend(["--description", description])
    if labels:
        args.extend(["--labels", labels])
    if assignee:
        args.extend(["--assignee", assignee])
    if notes:
        args.extend(["--notes", notes])
    if acceptance:
        args.extend(["--acceptance", acceptance])
    if thread:
        args.extend(["--thread", thread])

    # bd create doesn't have --json output that returns the issue,
    # so we parse the text output to get the ID, then show it.
    output = _run_bd(*args, workspace=workspace)

    # Parse "Created issue: gt-17" from output
    import re
    match = re.search(r"Created issue:\s*(\S+)", output)
    if match:
        return show_issue(match.group(1), workspace=workspace)

    # Fallback: try to extract any ID pattern
    match = re.search(r"([\w]+-\d+)", output)
    if match:
        return show_issue(match.group(1), workspace=workspace)

    raise ValueError(f"Could not parse issue ID from bd create output: {output[:300]}")


def show_issue(issue_id: str, *, workspace: str | Path | None = None) -> BeadsIssue:
    """Get full details of a single issue."""
    data = _run_bd("show", issue_id, json_output=True, workspace=workspace)
    if isinstance(data, list) and data:
        data = data[0]
    if isinstance(data, dict):
        return _parse_issue(data)
    raise ValueError(f"Unexpected bd show output for {issue_id}: {type(data)}")


def update_issue(issue_id: str, *, workspace: str | Path | None = None, **kwargs: Any) -> None:
    """Update issue fields.

    Supported kwargs:
        status, notes, append_notes, assignee, priority,
        add_label, remove_label, claim (bool).
    """
    args = ["update", issue_id]

    if kwargs.get("claim"):
        args.append("--claim")
    if "status" in kwargs:
        args.extend(["--status", kwargs["status"]])
    if "notes" in kwargs:
        args.extend(["--notes", kwargs["notes"]])
    if "append_notes" in kwargs:
        args.extend(["--append-notes", kwargs["append_notes"]])
    if "assignee" in kwargs:
        args.extend(["--assignee", kwargs["assignee"]])
    if "priority" in kwargs:
        args.extend(["--priority", str(kwargs["priority"])])
    if "add_label" in kwargs:
        args.extend(["--add-label", kwargs["add_label"]])
    if "remove_label" in kwargs:
        args.extend(["--remove-label", kwargs["remove_label"]])

    _run_bd(*args, workspace=workspace)


def close_issue(issue_id: str, reason: str | None = None, *, workspace: str | Path | None = None) -> None:
    """Close an issue."""
    args = ["close", issue_id]
    if reason:
        args.extend(["--reason", reason])
    _run_bd(*args, workspace=workspace)


def reopen_issue(issue_id: str, reason: str | None = None, *, workspace: str | Path | None = None) -> None:
    """Reopen a closed issue."""
    args = ["reopen", issue_id]
    if reason:
        args.extend(["--reason", reason])
    _run_bd(*args, workspace=workspace)


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


def list_issues(*, workspace: str | Path | None = None, **filters: Any) -> list[BeadsIssue]:
    """List issues with filters.

    Supported filters:
        status, label, label_any, assignee, issue_type (as 'type'),
        parent, priority, title, notes_contains, sort, reverse (bool),
        limit.
    """
    args = ["list"]
    _filter_map = {
        "status": "--status",
        "label": "--label",
        "label_any": "--label-any",
        "assignee": "--assignee",
        "issue_type": "--type",
        "parent": "--parent",
        "priority": "--priority",
        "title": "--title",
        "notes_contains": "--notes-contains",
        "sort": "--sort",
        "limit": "--limit",
    }
    for key, flag in _filter_map.items():
        if key in filters:
            args.extend([flag, str(filters[key])])
    if filters.get("reverse"):
        args.append("--reverse")
    if filters.get("no_assignee"):
        args.append("--no-assignee")

    data = _run_bd(*args, json_output=True, workspace=workspace)
    return _parse_issues(data)


def ready(*, assignee: str | None = None, unassigned: bool = False, workspace: str | Path | None = None) -> list[BeadsIssue]:
    """Get ready (unblocked, open) work."""
    args = ["ready"]
    if assignee:
        args.extend(["--assignee", assignee])
    if unassigned:
        args.append("--unassigned")

    data = _run_bd(*args, json_output=True, workspace=workspace)
    return _parse_issues(data)


def blocked(*, workspace: str | Path | None = None) -> list[BeadsIssue]:
    """Get blocked issues."""
    data = _run_bd("blocked", json_output=True, workspace=workspace)
    return _parse_issues(data)


def search(query: str, *, workspace: str | Path | None = None) -> list[BeadsIssue]:
    """Search issues by text."""
    data = _run_bd("search", query, json_output=True, workspace=workspace)
    return _parse_issues(data)


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def add_dependency(
    blocked_id: str, blocker_id: str, dep_type: str = "blocks",
    *, workspace: str | Path | None = None,
) -> None:
    """Add a dependency: blocker blocks blocked."""
    args = ["dep", "add", blocked_id, blocker_id]
    if dep_type != "blocks":
        args.extend(["--type", dep_type])
    _run_bd(*args, workspace=workspace)


def remove_dependency(issue_id: str, depends_on_id: str, *, workspace: str | Path | None = None) -> None:
    """Remove a dependency."""
    _run_bd("dep", "remove", issue_id, depends_on_id, workspace=workspace)


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------


def sync(*, force: bool = False, full: bool = False, import_mode: bool = False, workspace: str | Path | None = None) -> None:
    """Sync the Beads database."""
    args = ["sync"]
    if force:
        args.append("--force")
    if full:
        args.append("--full")
    if import_mode:
        args.append("--import")
    _run_bd(*args, workspace=workspace)
