"""Unit tests for the Bonobo Write Guards."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from orchestrator.lib.bonobo.audit import AuditLog, AuditEntry
from orchestrator.lib.bonobo.file_guard import FileGuard
from orchestrator.lib.bonobo.git_guard import GitGuard, GitStatus, MergeResult
from orchestrator.lib.bonobo.beads_guard import BeadsGuard, ValidationResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Create a minimal workspace with expected directories."""
    (tmp_path / ".beads").mkdir()
    (tmp_path / ".git").mkdir()
    (tmp_path / "aidlc-docs" / "inception").mkdir(parents=True)
    (tmp_path / "orchestrator" / "lib").mkdir(parents=True)
    (tmp_path / "tests" / "unit").mkdir(parents=True)
    (tmp_path / "templates").mkdir()
    (tmp_path / "docs").mkdir()
    return tmp_path


@pytest.fixture
def audit() -> AuditLog:
    """Create an audit log without Agent Mail."""
    return AuditLog()


@pytest.fixture
def file_guard(audit: AuditLog, workspace: Path) -> FileGuard:
    return FileGuard(audit, workspace_root=workspace)


@pytest.fixture
def git_guard(audit: AuditLog, workspace: Path) -> GitGuard:
    return GitGuard(audit, workspace_root=workspace)


@pytest.fixture
def beads_guard(audit: AuditLog) -> BeadsGuard:
    return BeadsGuard(audit)


# ---------------------------------------------------------------------------
# AuditLog tests
# ---------------------------------------------------------------------------


class TestAuditLog:
    def test_log_and_recent(self, audit: AuditLog):
        audit.log_allowed("file", "write_file", "Scout", {"path": "/tmp/test.md"})
        audit.log_denied("git", "commit", "Forge", "Protected branch", {"branch": "main"})

        entries = audit.recent(10)
        assert len(entries) == 2
        assert entries[0].result == "allowed"
        assert entries[1].result == "denied"

    def test_filter_by_agent(self, audit: AuditLog):
        audit.log_allowed("file", "write", "Scout", {})
        audit.log_allowed("file", "write", "Forge", {})
        audit.log_allowed("file", "write", "Scout", {})

        scout_entries = audit.filter_by_agent("Scout")
        assert len(scout_entries) == 2

    def test_filter_by_result(self, audit: AuditLog):
        audit.log_allowed("file", "write", "Scout", {})
        audit.log_denied("file", "write", "Forge", "reason", {})

        denied = audit.filter_by_result("denied")
        assert len(denied) == 1
        assert denied[0].agent == "Forge"

    def test_mail_failure_graceful(self):
        """REL-03: Audit must not fail when Agent Mail is unreachable."""
        mock_client = MagicMock()
        mock_client.send_message.side_effect = ConnectionError("Unreachable")
        audit = AuditLog(mail_client=mock_client, project_key="test")

        # Should not raise
        audit.log_allowed("file", "write", "Scout", {})
        assert len(audit.recent()) == 1
        assert len(audit._pending_flush) == 1


# ---------------------------------------------------------------------------
# FileGuard tests
# ---------------------------------------------------------------------------


class TestFileGuardValidation:
    def test_valid_markdown_in_aidlc_docs(self, file_guard: FileGuard, workspace: Path):
        result = file_guard.validate_path(workspace / "aidlc-docs" / "inception" / "test.md")
        assert result.allowed is True

    def test_deny_python_in_aidlc_docs(self, file_guard: FileGuard, workspace: Path):
        result = file_guard.validate_path(workspace / "aidlc-docs" / "evil.py")
        assert result.allowed is False
        assert "not allowed" in result.reason

    def test_deny_git_directory(self, file_guard: FileGuard, workspace: Path):
        result = file_guard.validate_path(workspace / ".git" / "config")
        assert result.allowed is False
        assert "forbidden" in result.reason.lower()

    def test_deny_beads_directory(self, file_guard: FileGuard, workspace: Path):
        result = file_guard.validate_path(workspace / ".beads" / "issues.jsonl")
        assert result.allowed is False

    def test_deny_hidden_files(self, file_guard: FileGuard, workspace: Path):
        result = file_guard.validate_path(workspace / ".env")
        assert result.allowed is False
        assert "hidden" in result.reason.lower()

    def test_deny_outside_workspace(self, file_guard: FileGuard, workspace: Path):
        result = file_guard.validate_path(Path("/etc/passwd"))
        assert result.allowed is False
        assert "outside workspace" in result.reason.lower()

    def test_deny_null_bytes(self, file_guard: FileGuard, workspace: Path):
        result = file_guard.validate_path(workspace / "test\x00.md")
        assert result.allowed is False
        assert "null" in result.reason.lower()

    def test_valid_python_in_orchestrator(self, file_guard: FileGuard, workspace: Path):
        result = file_guard.validate_path(workspace / "orchestrator" / "lib" / "test.py")
        assert result.allowed is True

    def test_deny_markdown_in_orchestrator(self, file_guard: FileGuard, workspace: Path):
        result = file_guard.validate_path(workspace / "orchestrator" / "readme.md")
        assert result.allowed is False


class TestFileGuardWrite:
    def test_write_valid_file(self, file_guard: FileGuard, workspace: Path, audit: AuditLog):
        path = file_guard.write_file(
            workspace / "aidlc-docs" / "inception" / "test.md",
            "# Test\n\nContent.\n",
            "Scout",
        )
        assert path.exists()
        assert path.read_text(encoding="utf-8") == "# Test\n\nContent.\n"
        assert audit.recent()[-1].result == "allowed"

    def test_deny_overwrite(self, file_guard: FileGuard, workspace: Path):
        file_guard.write_file(
            workspace / "aidlc-docs" / "inception" / "existing.md",
            "# Existing\n",
            "Scout",
        )
        with pytest.raises(FileExistsError):
            file_guard.write_file(
                workspace / "aidlc-docs" / "inception" / "existing.md",
                "# New\n",
                "Scout",
            )

    def test_allow_overwrite_flag(self, file_guard: FileGuard, workspace: Path):
        file_guard.write_file(
            workspace / "aidlc-docs" / "inception" / "rewrite.md",
            "# V1\n",
            "Scout",
        )
        path = file_guard.write_file(
            workspace / "aidlc-docs" / "inception" / "rewrite.md",
            "# V2\n",
            "Scout",
            overwrite=True,
        )
        assert "V2" in path.read_text(encoding="utf-8")

    def test_deny_forbidden_path(self, file_guard: FileGuard, workspace: Path, audit: AuditLog):
        with pytest.raises(PermissionError, match="denied"):
            file_guard.write_file(workspace / ".git" / "config", "bad", "Scout")
        assert audit.recent()[-1].result == "denied"

    def test_deny_oversized_code(self, file_guard: FileGuard, workspace: Path):
        huge = "x" * 600_000  # > 500KB
        with pytest.raises(PermissionError, match="exceeds limit"):
            file_guard.write_file(
                workspace / "orchestrator" / "big.py",
                huge,
                "Forge",
            )


class TestFileGuardDelete:
    def test_delete_valid_file(self, file_guard: FileGuard, workspace: Path, audit: AuditLog):
        target = workspace / "aidlc-docs" / "inception" / "delete-me.md"
        target.write_text("# Delete Me\n")
        file_guard.delete_file(target, "Scout")
        assert not target.exists()
        assert audit.recent()[-1].result == "allowed"

    def test_deny_protected_file(self, file_guard: FileGuard, workspace: Path):
        readme = workspace / "README.md"
        readme.write_text("# Readme\n")
        with pytest.raises(PermissionError, match="protected"):
            file_guard.delete_file(readme, "Scout")

    def test_not_found(self, file_guard: FileGuard, workspace: Path):
        with pytest.raises(FileNotFoundError):
            file_guard.delete_file(workspace / "nonexistent.md", "Scout")


# ---------------------------------------------------------------------------
# GitGuard tests
# ---------------------------------------------------------------------------


class TestGitGuard:
    @patch("orchestrator.lib.bonobo.git_guard.GitGuard._run_git")
    def test_get_status(self, mock_git, git_guard: GitGuard):
        mock_git.return_value = MagicMock(
            stdout="## aidlc/unit-1...origin/aidlc/unit-1\n",
            returncode=0,
        )
        status = git_guard.get_status()
        assert status.branch == "aidlc/unit-1"
        assert status.clean is True

    @patch("orchestrator.lib.bonobo.git_guard.GitGuard._run_git")
    def test_create_branch_valid(self, mock_git, git_guard: GitGuard, audit: AuditLog):
        mock_git.return_value = MagicMock(returncode=0)
        name = git_guard.create_branch("aidlc/unit-1-scribe", "ProjectMinder")
        assert name == "aidlc/unit-1-scribe"
        assert audit.recent()[-1].result == "allowed"

    def test_create_branch_no_prefix(self, git_guard: GitGuard, audit: AuditLog):
        with pytest.raises(PermissionError, match="aidlc/"):
            git_guard.create_branch("feature/bad", "Forge")
        assert audit.recent()[-1].result == "denied"

    @patch("orchestrator.lib.bonobo.git_guard.GitGuard._run_git")
    @patch("orchestrator.lib.bonobo.git_guard.GitGuard.get_status")
    def test_commit_on_protected_branch(self, mock_status, mock_git, git_guard: GitGuard):
        mock_status.return_value = GitStatus(branch="main", clean=True)
        with pytest.raises(PermissionError, match="protected branch"):
            git_guard.commit("Add file", [Path("test.py")], "Forge", "gt-19")

    @patch("orchestrator.lib.bonobo.git_guard.GitGuard._run_git")
    @patch("orchestrator.lib.bonobo.git_guard.GitGuard.get_status")
    def test_commit_auto_prepend_issue(self, mock_status, mock_git, git_guard: GitGuard, audit: AuditLog):
        mock_status.return_value = GitStatus(branch="aidlc/unit-1", clean=True)
        mock_git.return_value = MagicMock(stdout="abc123\n", returncode=0)

        git_guard.commit("Add functional design", [Path("test.md")], "Scout", "gt-17")
        # Message should have been prepended with [gt-17]
        last = audit.recent()[-1]
        assert last.result == "allowed"
        assert "gt-17" in last.details.get("message", "")

    @patch("orchestrator.lib.bonobo.git_guard.GitGuard._run_git")
    def test_merge_to_protected_denied(self, mock_git, git_guard: GitGuard):
        with pytest.raises(PermissionError, match="protected branch"):
            git_guard.merge("aidlc/unit-1", "main", "Forge")

    @patch("orchestrator.lib.bonobo.git_guard.GitGuard._run_git")
    def test_merge_success(self, mock_git, git_guard: GitGuard, audit: AuditLog):
        # First call: checkout target; second: merge; third: rev-parse
        mock_git.side_effect = [
            MagicMock(returncode=0),  # checkout
            MagicMock(returncode=0, stdout=""),  # merge
            MagicMock(stdout="def456\n", returncode=0),  # rev-parse
        ]
        result = git_guard.merge("aidlc/unit-1", "aidlc/integration", "ProjectMinder")
        assert result.success is True
        assert result.commit_hash == "def456"

    @patch("orchestrator.lib.bonobo.git_guard.GitGuard._run_git")
    def test_merge_conflicts(self, mock_git, git_guard: GitGuard):
        mock_git.side_effect = [
            MagicMock(returncode=0),  # checkout
            MagicMock(returncode=1, stdout="CONFLICT"),  # merge failed
            MagicMock(stdout="file1.py\nfile2.py\n", returncode=0),  # diff --name-only
            MagicMock(returncode=0),  # merge --abort
        ]
        result = git_guard.merge("aidlc/unit-1", "aidlc/integration", "ProjectMinder")
        assert result.success is False
        assert "file1.py" in result.conflicts


# ---------------------------------------------------------------------------
# BeadsGuard tests
# ---------------------------------------------------------------------------


class TestBeadsGuardValidation:
    def test_valid_create(self, beads_guard: BeadsGuard):
        result = beads_guard.validate_create(
            "Test Task", "task", ["phase:construction"], "Scout"
        )
        assert result.allowed is True

    def test_empty_title(self, beads_guard: BeadsGuard):
        result = beads_guard.validate_create("", "task", [], "Scout")
        assert result.allowed is False
        assert "empty" in result.reason.lower()

    def test_invalid_type(self, beads_guard: BeadsGuard):
        result = beads_guard.validate_create("Test", "invalid", [], "Scout")
        assert result.allowed is False
        assert "Invalid issue type" in result.reason

    def test_epic_denied_for_chimp(self, beads_guard: BeadsGuard):
        result = beads_guard.validate_create("Epic", "epic", [], "Scout")
        assert result.allowed is False
        assert "cannot create epics" in result.reason.lower()

    def test_epic_allowed_for_harmbe(self, beads_guard: BeadsGuard):
        result = beads_guard.validate_create("Epic", "epic", [], "Harmbe")
        assert result.allowed is True

    def test_invalid_label_prefix(self, beads_guard: BeadsGuard):
        result = beads_guard.validate_create("Test", "task", ["bogus:value"], "Scout")
        assert result.allowed is False
        assert "unknown prefix" in result.reason.lower()

    def test_valid_labels(self, beads_guard: BeadsGuard):
        result = beads_guard.validate_create(
            "Test", "task", ["phase:construction", "unit:scribe-library"], "Scout"
        )
        assert result.allowed is True


class TestBeadsGuardUpdate:
    @patch("orchestrator.lib.bonobo.beads_guard.show_issue")
    def test_valid_update(self, mock_show, beads_guard: BeadsGuard):
        from orchestrator.lib.beads.models import BeadsIssue
        mock_show.return_value = BeadsIssue(id="gt-5", title="Test", status="open", assignee="Scout")
        result = beads_guard.validate_update("gt-5", {"status": "in_progress"}, "Scout")
        assert result.allowed is True

    @patch("orchestrator.lib.bonobo.beads_guard.show_issue")
    def test_deny_update_other_agent(self, mock_show, beads_guard: BeadsGuard):
        from orchestrator.lib.beads.models import BeadsIssue
        mock_show.return_value = BeadsIssue(id="gt-5", title="Test", assignee="Forge")
        result = beads_guard.validate_update("gt-5", {"status": "done"}, "Scout")
        assert result.allowed is False
        assert "cannot update" in result.reason.lower()

    @patch("orchestrator.lib.bonobo.beads_guard.show_issue")
    def test_deny_change_type(self, mock_show, beads_guard: BeadsGuard):
        from orchestrator.lib.beads.models import BeadsIssue
        mock_show.return_value = BeadsIssue(id="gt-5", title="Test", assignee="Scout")
        result = beads_guard.validate_update("gt-5", {"issue_type": "epic"}, "Scout")
        assert result.allowed is False

    @patch("orchestrator.lib.bonobo.beads_guard.show_issue")
    def test_deny_remove_phase_label(self, mock_show, beads_guard: BeadsGuard):
        from orchestrator.lib.beads.models import BeadsIssue
        mock_show.return_value = BeadsIssue(id="gt-5", title="Test", assignee="Scout")
        result = beads_guard.validate_update("gt-5", {"remove_label": "phase:inception"}, "Scout")
        assert result.allowed is False

    @patch("orchestrator.lib.bonobo.beads_guard.show_issue")
    def test_deny_invalid_transition(self, mock_show, beads_guard: BeadsGuard):
        from orchestrator.lib.beads.models import BeadsIssue
        mock_show.return_value = BeadsIssue(id="gt-5", title="Test", status="done", assignee="Scout")
        result = beads_guard.validate_update("gt-5", {"status": "in_progress"}, "Scout")
        assert result.allowed is False
        assert "Invalid status transition" in result.reason

    @patch("orchestrator.lib.bonobo.beads_guard.show_issue")
    def test_issue_not_found(self, mock_show, beads_guard: BeadsGuard):
        mock_show.side_effect = subprocess.CalledProcessError(1, "bd")
        result = beads_guard.validate_update("gt-999", {"status": "done"}, "Scout")
        assert result.allowed is False
        assert "not found" in result.reason.lower()


class TestBeadsGuardDependency:
    @patch("orchestrator.lib.bonobo.beads_guard.show_issue")
    def test_valid_dependency(self, mock_show, beads_guard: BeadsGuard):
        from orchestrator.lib.beads.models import BeadsIssue
        mock_show.return_value = BeadsIssue(id="gt-5", title="Test")
        with patch("subprocess.run"):
            result = beads_guard.validate_dependency("gt-5", "gt-4", "blocks", "ProjectMinder")
        assert result.allowed is True

    @patch("orchestrator.lib.bonobo.beads_guard.show_issue")
    def test_issue_not_found(self, mock_show, beads_guard: BeadsGuard):
        mock_show.side_effect = subprocess.CalledProcessError(1, "bd")
        result = beads_guard.validate_dependency("gt-999", "gt-4", "blocks", "ProjectMinder")
        assert result.allowed is False
