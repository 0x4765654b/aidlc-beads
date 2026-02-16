"""Unit tests for the Beads CLI client library."""

from __future__ import annotations

import json
import subprocess
from unittest.mock import patch, MagicMock

import pytest

from orchestrator.lib.beads.client import (
    _run_bd,
    create_issue,
    show_issue,
    update_issue,
    close_issue,
    reopen_issue,
    list_issues,
    ready,
    blocked,
    search,
    add_dependency,
    remove_dependency,
    sync,
)
from orchestrator.lib.beads.models import BeadsIssue


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_ISSUE_JSON = {
    "id": "gt-5",
    "title": "Requirements Analysis",
    "status": "open",
    "priority": 1,
    "type": "task",
    "assignee": None,
    "labels": ["phase:inception"],
    "notes": "artifact: aidlc-docs/inception/requirements/requirements.md",
    "description": "Analyze requirements.",
    "created_at": "2026-02-15T10:00:00Z",
    "updated_at": None,
}


def _mock_run(stdout: str = "", returncode: int = 0):
    """Create a mock subprocess.run result."""
    result = MagicMock()
    result.stdout = stdout
    result.stderr = ""
    result.returncode = returncode
    return result


# ---------------------------------------------------------------------------
# _run_bd tests
# ---------------------------------------------------------------------------


class TestRunBd:
    @patch("subprocess.run")
    def test_run_plain(self, mock_run):
        mock_run.return_value = _mock_run("hello world")
        result = _run_bd("status")
        assert result == "hello world"
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "bd"
        assert "status" in args

    @patch("subprocess.run")
    def test_run_json(self, mock_run):
        mock_run.return_value = _mock_run(json.dumps({"id": "gt-1"}))
        result = _run_bd("show", "gt-1", json_output=True)
        assert result == {"id": "gt-1"}
        args = mock_run.call_args[0][0]
        assert "--json" in args

    @patch("subprocess.run", side_effect=FileNotFoundError)
    def test_bd_not_found(self, mock_run):
        with pytest.raises(RuntimeError, match="not found on PATH"):
            _run_bd("status")

    @patch("subprocess.run")
    def test_json_parse_failure(self, mock_run):
        mock_run.return_value = _mock_run("not json")
        with pytest.raises(ValueError, match="Failed to parse"):
            _run_bd("show", "gt-1", json_output=True)


# ---------------------------------------------------------------------------
# BeadsIssue model tests
# ---------------------------------------------------------------------------


class TestBeadsIssue:
    def test_from_json(self):
        issue = BeadsIssue.from_json(SAMPLE_ISSUE_JSON)
        assert issue.id == "gt-5"
        assert issue.title == "Requirements Analysis"
        assert issue.status == "open"
        assert issue.priority == 1
        assert issue.issue_type == "task"
        assert "phase:inception" in issue.labels

    def test_from_json_minimal(self):
        issue = BeadsIssue.from_json({"id": "gt-1", "title": "Test"})
        assert issue.id == "gt-1"
        assert issue.status == "open"
        assert issue.priority == 2


# ---------------------------------------------------------------------------
# CRUD function tests
# ---------------------------------------------------------------------------


class TestShowIssue:
    @patch("orchestrator.lib.beads.client._run_bd")
    def test_show(self, mock_bd):
        mock_bd.return_value = SAMPLE_ISSUE_JSON
        issue = show_issue("gt-5")
        assert issue.id == "gt-5"
        assert issue.title == "Requirements Analysis"
        mock_bd.assert_called_once_with("show", "gt-5", json_output=True)


class TestCreateIssue:
    @patch("orchestrator.lib.beads.client.show_issue")
    @patch("orchestrator.lib.beads.client._run_bd")
    def test_create(self, mock_bd, mock_show):
        mock_bd.return_value = "✓ Created issue: gt-99\n  Title: New Task"
        mock_show.return_value = BeadsIssue(id="gt-99", title="New Task")
        issue = create_issue("New Task", "task", 1, description="Desc")
        assert issue.id == "gt-99"
        args = mock_bd.call_args[0]
        assert "create" in args
        assert "New Task" in args
        assert "-t" in args
        assert "task" in args

    @patch("orchestrator.lib.beads.client._run_bd")
    def test_create_parse_failure(self, mock_bd):
        mock_bd.return_value = "Some unexpected output"
        with pytest.raises(ValueError, match="Could not parse issue ID"):
            create_issue("Bad", "task", 1)


class TestUpdateIssue:
    @patch("orchestrator.lib.beads.client._run_bd")
    def test_update_status(self, mock_bd):
        mock_bd.return_value = "Updated"
        update_issue("gt-5", status="done")
        args = mock_bd.call_args[0]
        assert "--status" in args
        assert "done" in args

    @patch("orchestrator.lib.beads.client._run_bd")
    def test_update_claim(self, mock_bd):
        mock_bd.return_value = "Updated"
        update_issue("gt-5", claim=True)
        args = mock_bd.call_args[0]
        assert "--claim" in args

    @patch("orchestrator.lib.beads.client._run_bd")
    def test_update_append_notes(self, mock_bd):
        mock_bd.return_value = "Updated"
        update_issue("gt-5", append_notes="New note")
        args = mock_bd.call_args[0]
        assert "--append-notes" in args


class TestCloseIssue:
    @patch("orchestrator.lib.beads.client._run_bd")
    def test_close(self, mock_bd):
        mock_bd.return_value = "Closed"
        close_issue("gt-5", reason="Done")
        args = mock_bd.call_args[0]
        assert "close" in args
        assert "--reason" in args


class TestReopenIssue:
    @patch("orchestrator.lib.beads.client._run_bd")
    def test_reopen(self, mock_bd):
        mock_bd.return_value = "Reopened"
        reopen_issue("gt-5")
        args = mock_bd.call_args[0]
        assert "reopen" in args


# ---------------------------------------------------------------------------
# Query function tests
# ---------------------------------------------------------------------------


class TestListIssues:
    @patch("orchestrator.lib.beads.client._run_bd")
    def test_list_with_filters(self, mock_bd):
        mock_bd.return_value = [SAMPLE_ISSUE_JSON]
        issues = list_issues(status="open", label="phase:inception")
        assert len(issues) == 1
        assert issues[0].id == "gt-5"
        args = mock_bd.call_args
        positional = args[0]
        assert "--status" in positional
        assert "--label" in positional

    @patch("orchestrator.lib.beads.client._run_bd")
    def test_list_dict_wrapper(self, mock_bd):
        mock_bd.return_value = {"issues": [SAMPLE_ISSUE_JSON]}
        issues = list_issues()
        assert len(issues) == 1


class TestReady:
    @patch("orchestrator.lib.beads.client._run_bd")
    def test_ready(self, mock_bd):
        mock_bd.return_value = [SAMPLE_ISSUE_JSON]
        issues = ready()
        assert len(issues) == 1

    @patch("orchestrator.lib.beads.client._run_bd")
    def test_ready_with_assignee(self, mock_bd):
        mock_bd.return_value = []
        issues = ready(assignee="human")
        assert issues == []
        args = mock_bd.call_args[0]
        assert "--assignee" in args


class TestBlocked:
    @patch("orchestrator.lib.beads.client._run_bd")
    def test_blocked(self, mock_bd):
        mock_bd.return_value = []
        issues = blocked()
        assert issues == []


class TestSearch:
    @patch("orchestrator.lib.beads.client._run_bd")
    def test_search(self, mock_bd):
        mock_bd.return_value = [SAMPLE_ISSUE_JSON]
        issues = search("requirements")
        assert len(issues) == 1


# ---------------------------------------------------------------------------
# Dependency function tests
# ---------------------------------------------------------------------------


class TestDependencies:
    @patch("orchestrator.lib.beads.client._run_bd")
    def test_add_dep(self, mock_bd):
        mock_bd.return_value = "Added"
        add_dependency("gt-5", "gt-4")
        args = mock_bd.call_args[0]
        assert "dep" in args
        assert "add" in args
        assert "gt-5" in args
        assert "gt-4" in args

    @patch("orchestrator.lib.beads.client._run_bd")
    def test_add_dep_with_type(self, mock_bd):
        mock_bd.return_value = "Added"
        add_dependency("gt-5", "gt-1", dep_type="parent")
        args = mock_bd.call_args[0]
        assert "--type" in args
        assert "parent" in args

    @patch("orchestrator.lib.beads.client._run_bd")
    def test_remove_dep(self, mock_bd):
        mock_bd.return_value = "Removed"
        remove_dependency("gt-5", "gt-4")


# ---------------------------------------------------------------------------
# Sync tests
# ---------------------------------------------------------------------------


class TestSync:
    @patch("orchestrator.lib.beads.client._run_bd")
    def test_sync_basic(self, mock_bd):
        mock_bd.return_value = "Synced"
        sync()
        args = mock_bd.call_args[0]
        assert "sync" in args

    @patch("orchestrator.lib.beads.client._run_bd")
    def test_sync_full(self, mock_bd):
        mock_bd.return_value = "Synced"
        sync(full=True)
        args = mock_bd.call_args[0]
        assert "--full" in args
