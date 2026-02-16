"""GitGuard -- validates and executes Git operations."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from orchestrator.lib.bonobo.audit import AuditLog
from orchestrator.lib.scribe.workspace import find_workspace_root

AIDLC_BRANCH_PREFIX = "aidlc/"
PROTECTED_BRANCHES = frozenset({"main", "master", "develop"})
COMMIT_MESSAGE_PATTERN = re.compile(r"^\[[\w.-]+\]\s.+")
BRANCH_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9/\-_.]*$")


@dataclass
class GitStatus:
    """Current Git repository status."""

    branch: str
    clean: bool
    staged: list[str] = field(default_factory=list)
    modified: list[str] = field(default_factory=list)
    untracked: list[str] = field(default_factory=list)


@dataclass
class MergeResult:
    """Result of a Git merge operation."""

    success: bool
    commit_hash: str | None = None
    conflicts: list[str] = field(default_factory=list)
    strategy_used: str = "merge"


class GitGuard:
    """Validates and executes Git operations.

    All Git operations by agents flow through this guard.
    """

    def __init__(self, audit: AuditLog, workspace_root: Path | None = None) -> None:
        self._audit = audit
        self._root = workspace_root or find_workspace_root()

    def _run_git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        """Run a git command in the workspace."""
        try:
            return subprocess.run(
                ["git", *args],
                capture_output=True,
                text=True,
                check=check,
                cwd=str(self._root),
            )
        except FileNotFoundError:
            raise RuntimeError("git is not found on PATH") from None

    def get_status(self) -> GitStatus:
        """Get current Git status."""
        result = self._run_git("status", "--porcelain", "-b")
        lines = result.stdout.strip().split("\n") if result.stdout.strip() else []

        branch = "unknown"
        staged = []
        modified = []
        untracked = []

        for line in lines:
            if line.startswith("## "):
                # Parse branch name from "## main...origin/main"
                branch_part = line[3:].split("...")[0].strip()
                branch = branch_part
            elif line.startswith("??"):
                untracked.append(line[3:].strip())
            elif line[0] in ("M", "A", "D", "R", "C"):
                staged.append(line[3:].strip())
            elif len(line) > 1 and line[1] in ("M", "D"):
                modified.append(line[3:].strip())

        clean = not staged and not modified and not untracked

        return GitStatus(
            branch=branch,
            clean=clean,
            staged=staged,
            modified=modified,
            untracked=untracked,
        )

    def create_branch(self, branch_name: str, agent: str, base: str = "main") -> str:
        """Create a new Git branch.

        Args:
            branch_name: Name for the new branch.
            agent: Name of the requesting agent.
            base: Base branch to create from.

        Returns:
            The created branch name.

        Raises:
            PermissionError: If branch name doesn't follow conventions.
        """
        details = {"branch": branch_name, "base": base}

        # Must use aidlc/ prefix
        if not branch_name.startswith(AIDLC_BRANCH_PREFIX):
            reason = f"Agent branches must use '{AIDLC_BRANCH_PREFIX}' prefix"
            self._audit.log_denied("git", "create_branch", agent, reason, details)
            raise PermissionError(f"GitGuard denied: {reason}")

        # Valid characters
        if not BRANCH_NAME_PATTERN.match(branch_name):
            reason = f"Invalid branch name: {branch_name}"
            self._audit.log_denied("git", "create_branch", agent, reason, details)
            raise PermissionError(f"GitGuard denied: {reason}")

        self._run_git("checkout", "-b", branch_name, base)
        self._audit.log_allowed("git", "create_branch", agent, details)
        return branch_name

    def checkout_branch(self, branch_name: str, agent: str) -> None:
        """Switch to a branch.

        Args:
            branch_name: Branch to switch to.
            agent: Name of the requesting agent.

        Raises:
            PermissionError: If working tree is dirty.
        """
        details = {"branch": branch_name}

        # Check clean working tree
        status = self.get_status()
        if not status.clean:
            reason = "Working tree is not clean -- commit or stash changes first"
            self._audit.log_denied("git", "checkout_branch", agent, reason, details)
            raise PermissionError(f"GitGuard denied: {reason}")

        self._run_git("checkout", branch_name)
        self._audit.log_allowed("git", "checkout_branch", agent, details)

    def commit(
        self,
        message: str,
        files: list[Path],
        agent: str,
        issue_id: str,
    ) -> str:
        """Create a Git commit.

        Args:
            message: Commit message.
            files: Files to stage and commit.
            agent: Name of the requesting agent.
            issue_id: Beads issue ID for traceability.

        Returns:
            The commit hash.

        Raises:
            PermissionError: If on protected branch or message is invalid.
        """
        details = {
            "message": message,
            "files": [str(f) for f in files],
            "issue_id": issue_id,
        }

        # SEC-05: No commits to protected branches
        status = self.get_status()
        if status.branch in PROTECTED_BRANCHES:
            reason = f"Cannot commit to protected branch: {status.branch}"
            self._audit.log_denied("git", "commit", agent, reason, details)
            raise PermissionError(f"GitGuard denied: {reason}")

        # SEC-06: Commit message must reference issue
        if not COMMIT_MESSAGE_PATTERN.match(message):
            # Auto-prepend issue ID if missing
            message = f"[{issue_id}] {message}"

        # Verify message now matches
        if not COMMIT_MESSAGE_PATTERN.match(message):
            reason = f"Commit message doesn't match pattern [issue-id] description: {message}"
            self._audit.log_denied("git", "commit", agent, reason, details)
            raise PermissionError(f"GitGuard denied: {reason}")

        # Stage only specified files
        for f in files:
            file_path = Path(f)
            if not file_path.is_absolute():
                file_path = self._root / file_path
            self._run_git("add", str(file_path))

        # Commit
        result = self._run_git("commit", "-m", message)

        # Extract commit hash
        hash_result = self._run_git("rev-parse", "HEAD")
        commit_hash = hash_result.stdout.strip()

        details["commit_hash"] = commit_hash
        details["message"] = message
        self._audit.log_allowed("git", "commit", agent, details)
        return commit_hash

    def merge(
        self,
        source: str,
        target: str,
        agent: str,
        strategy: str = "merge",
    ) -> MergeResult:
        """Merge one branch into another.

        Args:
            source: Branch to merge from.
            target: Branch to merge into.
            agent: Name of the requesting agent.
            strategy: Merge strategy ("merge" or "rebase").

        Returns:
            MergeResult with success flag and any conflicts.

        Raises:
            PermissionError: If target is a protected branch.
        """
        details = {"source": source, "target": target, "strategy": strategy}

        # SEC-05: No merges to protected branches
        if target in PROTECTED_BRANCHES:
            reason = f"Cannot merge to protected branch: {target}"
            self._audit.log_denied("git", "merge", agent, reason, details)
            raise PermissionError(f"GitGuard denied: {reason}")

        # Checkout target
        self._run_git("checkout", target)

        # Attempt merge
        result = self._run_git("merge", source, "--no-edit", check=False)

        if result.returncode == 0:
            hash_result = self._run_git("rev-parse", "HEAD")
            merge_result = MergeResult(
                success=True,
                commit_hash=hash_result.stdout.strip(),
                strategy_used=strategy,
            )
            self._audit.log_allowed("git", "merge", agent, details)
            return merge_result

        # Merge failed -- find conflicts
        conflicts = []
        status_result = self._run_git("diff", "--name-only", "--diff-filter=U", check=False)
        if status_result.stdout.strip():
            conflicts = status_result.stdout.strip().split("\n")

        # REL-02: Abort the merge to leave repo clean
        self._run_git("merge", "--abort", check=False)

        merge_result = MergeResult(
            success=False,
            conflicts=conflicts,
            strategy_used=strategy,
        )
        self._audit.log_denied(
            "git", "merge", agent,
            f"Merge conflicts in: {conflicts}",
            details,
        )
        return merge_result

    def get_diff(self, path: Path | None = None) -> str:
        """Get diff output.

        Args:
            path: Optional file to restrict diff to.

        Returns:
            Diff output string.
        """
        args = ["diff"]
        if path:
            args.append(str(path))
        result = self._run_git(*args)
        return result.stdout
