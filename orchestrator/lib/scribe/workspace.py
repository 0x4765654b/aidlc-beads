"""Workspace root detection for Scribe."""

from __future__ import annotations

from pathlib import Path

AIDLC_DOCS_DIR = "aidlc-docs"
TEMPLATES_DIR = "templates"
SYNC_SCRIPT = "scripts/sync-outline.py"
MAX_PARENT_SEARCH = 10


def find_workspace_root(start: Path | None = None) -> Path:
    """Walk up from start (default: cwd) until .beads/ directory is found.

    Args:
        start: Directory to start searching from. Defaults to cwd.

    Returns:
        Path to the workspace root (directory containing .beads/).

    Raises:
        RuntimeError: If .beads/ is not found within MAX_PARENT_SEARCH levels.
    """
    current = (start or Path.cwd()).resolve()

    for _ in range(MAX_PARENT_SEARCH):
        if (current / ".beads").is_dir():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent

    raise RuntimeError(
        f"Not in a Beads workspace: .beads/ directory not found within "
        f"{MAX_PARENT_SEARCH} parent directories of {start or Path.cwd()}"
    )
