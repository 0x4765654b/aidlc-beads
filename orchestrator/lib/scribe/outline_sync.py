"""Outline Wiki sync wrappers."""

from __future__ import annotations

import subprocess
import sys

from orchestrator.lib.scribe.workspace import find_workspace_root, SYNC_SCRIPT


def _run_sync_command(command: str) -> str:
    """Run a sync-outline.py command and return stdout.

    Args:
        command: The sync command (push, pull, status, init, sync).

    Returns:
        stdout output from the script.

    Raises:
        RuntimeError: If the sync script fails.
    """
    root = find_workspace_root()
    script_path = root / SYNC_SCRIPT

    if not script_path.exists():
        raise RuntimeError(f"Outline sync script not found: {script_path}")

    result = subprocess.run(
        [sys.executable, str(script_path), command],
        capture_output=True,
        text=True,
        cwd=str(root),
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Outline sync '{command}' failed (exit code {result.returncode}):\n"
            f"{result.stderr.strip()}"
        )

    return result.stdout


def sync_to_outline() -> None:
    """Push local artifacts to Outline Wiki.

    Raises:
        RuntimeError: If the sync script fails or is not found.
    """
    _run_sync_command("push")


def pull_from_outline() -> None:
    """Pull edits from Outline back to local files.

    Raises:
        RuntimeError: If the sync script fails or is not found.
    """
    _run_sync_command("pull")


def outline_sync_status() -> str:
    """Get the current Outline sync status.

    Returns:
        Status output from the sync script.

    Raises:
        RuntimeError: If the sync script fails or is not found.
    """
    return _run_sync_command("status")
