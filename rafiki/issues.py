"""Beads issue filing via bd CLI."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from rafiki.models import FiledIssue

logger = logging.getLogger("rafiki.issues")

_ISSUE_ID_PATTERN = re.compile(r"([a-z]{2}-\d+)")


def _parse_issue_id(output: str) -> str:
    """Extract issue ID (e.g. gt-120) from bd create output."""
    match = _ISSUE_ID_PATTERN.search(output)
    return match.group(1) if match else ""


async def _run_bd(args: list[str], cwd: Path | None = None) -> str:
    """Run a bd CLI command and return stdout."""
    cmd = ["bd"] + args
    logger.debug("Running: %s", " ".join(cmd))
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )
    stdout, stderr = await proc.communicate()
    out = stdout.decode("utf-8", errors="replace").strip()
    if proc.returncode != 0:
        err = stderr.decode("utf-8", errors="replace").strip()
        logger.error("bd command failed (exit %d): %s\nstderr: %s", proc.returncode, " ".join(cmd), err)
        return ""
    return out


class IssueFiler:
    """Files Beads issues for problems Rafiki discovers."""

    def __init__(self, workspace_root: Path, run_id: str):
        self.workspace_root = workspace_root
        self.run_id = run_id
        self.filed: list[FiledIssue] = []

    async def _find_existing_bug(self, title: str) -> str | None:
        """Check if a Rafiki bug with a matching title already exists.

        Returns the issue ID if found, None otherwise.
        """
        output = await _run_bd([
            "list", "--label", "discovered-by:rafiki", "--status", "open", "--json",
        ], cwd=self.workspace_root)
        if not output:
            return None
        try:
            issues = json.loads(output)
        except json.JSONDecodeError:
            logger.warning("Could not parse bd list JSON output")
            return None

        normalized = title.lower().strip()
        for issue in issues:
            existing_title = issue.get("title", "")
            # Strip the "Rafiki: " prefix for comparison
            compare = existing_title.lower().strip()
            if compare.startswith("rafiki: "):
                compare = compare[len("rafiki: "):]
            if compare == normalized:
                return issue.get("id", "")
        return None

    def _build_labels(self, source: str, extra: list[str] | None) -> list[str]:
        labels = ["discovered-by:rafiki", f"rafiki-run:{self.run_id}"]
        if source:
            labels.append(f"discovered-from:{source}")
        if extra:
            labels.extend(extra)
        return labels

    async def file_bug(
        self,
        title: str,
        description: str,
        priority: int = 1,
        labels: list[str] | None = None,
        source: str = "",
    ) -> str:
        """File a bug issue via bd create. Returns the issue ID."""
        # Check for an existing open bug with the same title
        existing_id = await self._find_existing_bug(title)
        if existing_id:
            logger.info("Duplicate bug detected -- appending to %s instead of filing new issue", existing_id)
            await _run_bd([
                "comments", "add", existing_id,
                f"[Rafiki run {self.run_id}] Duplicate detection:\n\n{description}",
            ], cwd=self.workspace_root)
            return existing_id

        all_labels = self._build_labels(source, labels)
        result = await _run_bd([
            "create", f"Rafiki: {title}",
            "-t", "bug",
            "-p", str(priority),
            "--description", description,
            "--labels", ",".join(all_labels),
        ], cwd=self.workspace_root)
        issue_id = _parse_issue_id(result)
        if issue_id:
            filed = FiledIssue(
                issue_id=issue_id, title=f"Rafiki: {title}",
                type="bug", priority=priority, source=source,
            )
            self.filed.append(filed)
            logger.info("Filed bug %s: %s", issue_id, title)
        else:
            logger.error("Failed to file bug: %s (output: %s)", title, result)
        return issue_id

    async def file_task(
        self,
        title: str,
        description: str,
        priority: int = 2,
        labels: list[str] | None = None,
        source: str = "",
    ) -> str:
        """File a follow-up task via bd create. Returns the issue ID."""
        all_labels = self._build_labels(source, labels)
        result = await _run_bd([
            "create", f"Rafiki: {title}",
            "-t", "task",
            "-p", str(priority),
            "--description", description,
            "--labels", ",".join(all_labels),
        ], cwd=self.workspace_root)
        issue_id = _parse_issue_id(result)
        if issue_id:
            filed = FiledIssue(
                issue_id=issue_id, title=f"Rafiki: {title}",
                type="task", priority=priority, source=source,
            )
            self.filed.append(filed)
            logger.info("Filed task %s: %s", issue_id, title)
        else:
            logger.error("Failed to file task: %s (output: %s)", title, result)
        return issue_id
