"""Unit tests for the Scribe tool library."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from orchestrator.lib.scribe.models import ArtifactHeader, ValidationResult
from orchestrator.lib.scribe.headers import parse_header, write_header, strip_header
from orchestrator.lib.scribe.artifacts import (
    create_artifact,
    update_artifact,
    validate_artifact,
    list_stage_artifacts,
)
from orchestrator.lib.scribe.workspace import find_workspace_root
from orchestrator.lib.scribe.templates import apply_template


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Create a minimal Beads workspace in a temp directory."""
    beads_dir = tmp_path / ".beads"
    beads_dir.mkdir()
    (beads_dir / "config.yaml").write_text("prefix: test\n")

    aidlc_docs = tmp_path / "aidlc-docs"
    aidlc_docs.mkdir()

    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()

    return tmp_path


@pytest.fixture
def sample_artifact_content() -> str:
    return "# Sample Document\n\nThis is a sample artifact.\n"


# ---------------------------------------------------------------------------
# headers.py tests
# ---------------------------------------------------------------------------


class TestParseHeader:
    def test_parse_both_headers(self):
        content = (
            "<!-- beads-issue: gt-17 -->\n"
            "<!-- beads-review: gt-18 -->\n"
            "# Title\n"
        )
        header = parse_header(content)
        assert header.beads_issue == "gt-17"
        assert header.beads_review == "gt-18"

    def test_parse_issue_only(self):
        content = "<!-- beads-issue: ab-0042.3 -->\n# Title\n"
        header = parse_header(content)
        assert header.beads_issue == "ab-0042.3"
        assert header.beads_review is None

    def test_parse_with_blank_lines(self):
        content = (
            "<!-- beads-issue: gt-5 -->\n"
            "\n"
            "<!-- beads-review: gt-16 -->\n"
            "\n"
            "# Title\n"
        )
        header = parse_header(content)
        assert header.beads_issue == "gt-5"
        assert header.beads_review == "gt-16"

    def test_missing_issue_raises(self):
        content = "# Title\n\nNo headers here.\n"
        with pytest.raises(ValueError, match="Missing required beads-issue header"):
            parse_header(content)

    def test_empty_content_raises(self):
        with pytest.raises(ValueError):
            parse_header("")


class TestWriteHeader:
    def test_write_both(self):
        result = write_header("gt-17", "gt-18")
        assert "<!-- beads-issue: gt-17 -->" in result
        assert "<!-- beads-review: gt-18 -->" in result

    def test_write_issue_only(self):
        result = write_header("gt-5")
        assert "<!-- beads-issue: gt-5 -->" in result
        assert "beads-review" not in result

    def test_ends_with_newline(self):
        result = write_header("gt-1")
        assert result.endswith("\n")


class TestStripHeader:
    def test_strip_both_headers(self):
        content = (
            "<!-- beads-issue: gt-17 -->\n"
            "<!-- beads-review: gt-18 -->\n"
            "# Title\n"
            "Body text.\n"
        )
        body = strip_header(content)
        assert body.startswith("# Title")
        assert "beads-issue" not in body

    def test_strip_with_blank_lines(self):
        content = (
            "<!-- beads-issue: gt-5 -->\n"
            "\n"
            "# Title\n"
        )
        body = strip_header(content)
        assert body.startswith("# Title")

    def test_no_headers(self):
        content = "# Title\nBody.\n"
        body = strip_header(content)
        assert body == content


# ---------------------------------------------------------------------------
# workspace.py tests
# ---------------------------------------------------------------------------


class TestFindWorkspaceRoot:
    def test_finds_root(self, workspace: Path):
        # Search from a subdirectory
        subdir = workspace / "aidlc-docs" / "inception"
        subdir.mkdir(parents=True, exist_ok=True)
        root = find_workspace_root(subdir)
        assert root == workspace

    def test_finds_root_from_root(self, workspace: Path):
        root = find_workspace_root(workspace)
        assert root == workspace

    def test_not_found_raises(self, tmp_path: Path):
        with pytest.raises(RuntimeError, match="Not in a Beads workspace"):
            find_workspace_root(tmp_path)


# ---------------------------------------------------------------------------
# artifacts.py tests
# ---------------------------------------------------------------------------


class TestCreateArtifact:
    def test_creates_file(self, workspace: Path, sample_artifact_content: str):
        with patch("orchestrator.lib.scribe.artifacts.find_workspace_root", return_value=workspace):
            path = create_artifact(
                stage="requirements",
                name="requirements",
                content=sample_artifact_content,
                beads_issue_id="gt-5",
                review_gate_id="gt-16",
                phase="inception",
            )

        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "<!-- beads-issue: gt-5 -->" in content
        assert "<!-- beads-review: gt-16 -->" in content
        assert "# Sample Document" in content

    def test_creates_directory_structure(self, workspace: Path, sample_artifact_content: str):
        with patch("orchestrator.lib.scribe.artifacts.find_workspace_root", return_value=workspace):
            path = create_artifact(
                stage="unit-1-scribe",
                name="functional-design",
                content=sample_artifact_content,
                beads_issue_id="gt-17",
                phase="construction",
            )

        expected = workspace / "aidlc-docs" / "construction" / "unit-1-scribe" / "functional-design.md"
        assert path == expected

    def test_raises_on_existing_file(self, workspace: Path, sample_artifact_content: str):
        with patch("orchestrator.lib.scribe.artifacts.find_workspace_root", return_value=workspace):
            create_artifact("test-stage", "test-file", sample_artifact_content, "gt-1")
            with pytest.raises(FileExistsError):
                create_artifact("test-stage", "test-file", sample_artifact_content, "gt-1")

    def test_rejects_invalid_name(self, workspace: Path):
        with patch("orchestrator.lib.scribe.artifacts.find_workspace_root", return_value=workspace):
            with pytest.raises(ValueError, match="Invalid"):
                create_artifact("Bad Stage", "file", "content", "gt-1")

    def test_rejects_invalid_phase(self, workspace: Path):
        with patch("orchestrator.lib.scribe.artifacts.find_workspace_root", return_value=workspace):
            with pytest.raises(ValueError, match="Invalid phase"):
                create_artifact("stage", "file", "content", "gt-1", phase="invalid")


class TestUpdateArtifact:
    def test_updates_body_preserves_headers(self, workspace: Path, sample_artifact_content: str):
        with patch("orchestrator.lib.scribe.artifacts.find_workspace_root", return_value=workspace):
            path = create_artifact("test-stage", "test-doc", sample_artifact_content, "gt-1", "gt-2")
            update_artifact(path, "# Updated Title\n\nNew body.\n")

        content = path.read_text(encoding="utf-8")
        assert "<!-- beads-issue: gt-1 -->" in content
        assert "<!-- beads-review: gt-2 -->" in content
        assert "# Updated Title" in content
        assert "Sample Document" not in content

    def test_raises_on_missing_file(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            update_artifact(tmp_path / "nonexistent.md", "content")


class TestValidateArtifact:
    def test_valid_artifact(self, workspace: Path, sample_artifact_content: str):
        with patch("orchestrator.lib.scribe.artifacts.find_workspace_root", return_value=workspace):
            path = create_artifact("test-stage", "valid", sample_artifact_content, "gt-1", "gt-2")
            result = validate_artifact(path)

        assert result.valid is True
        assert len(result.errors) == 0

    def test_missing_file(self, tmp_path: Path):
        result = validate_artifact(tmp_path / "missing.md")
        assert result.valid is False
        assert "does not exist" in result.errors[0]

    def test_empty_file(self, tmp_path: Path):
        empty_file = tmp_path / "empty.md"
        empty_file.write_text("")
        result = validate_artifact(empty_file)
        assert result.valid is False
        assert "empty" in result.errors[0].lower()

    def test_missing_header(self, tmp_path: Path):
        bad_file = tmp_path / "no-header.md"
        bad_file.write_text("# Title\n\nNo header.\n")
        result = validate_artifact(bad_file)
        assert result.valid is False
        assert any("beads-issue" in e.lower() for e in result.errors)

    def test_missing_h1(self, workspace: Path):
        with patch("orchestrator.lib.scribe.artifacts.find_workspace_root", return_value=workspace):
            path = create_artifact("test-stage", "no-h1", "No heading here.\n", "gt-1")
            result = validate_artifact(path)

        assert result.valid is False
        assert any("H1" in e for e in result.errors)


class TestListStageArtifacts:
    def test_lists_artifacts(self, workspace: Path, sample_artifact_content: str):
        with patch("orchestrator.lib.scribe.artifacts.find_workspace_root", return_value=workspace):
            create_artifact("test-stage", "doc-a", "# Doc A\n\nContent A.\n", "gt-1")
            create_artifact("test-stage", "doc-b", "# Doc B\n\nContent B.\n", "gt-2")
            artifacts = list_stage_artifacts("test-stage")

        assert len(artifacts) == 2
        assert artifacts[0].title == "Doc A"
        assert artifacts[1].title == "Doc B"
        assert artifacts[0].stage == "test-stage"

    def test_empty_directory_returns_empty(self, workspace: Path):
        with patch("orchestrator.lib.scribe.artifacts.find_workspace_root", return_value=workspace):
            artifacts = list_stage_artifacts("nonexistent-stage")
        assert artifacts == []


# ---------------------------------------------------------------------------
# templates.py tests
# ---------------------------------------------------------------------------


class TestApplyTemplate:
    def test_fills_variables(self, workspace: Path):
        template_path = workspace / "templates" / "test-template.md"
        template_path.write_text("Issue: {issue_id}\nTitle: {title}\n")

        with patch("orchestrator.lib.scribe.templates.find_workspace_root", return_value=workspace):
            result = apply_template("test-template.md", {"issue_id": "gt-5", "title": "My Doc"})

        assert result == "Issue: gt-5\nTitle: My Doc\n"

    def test_missing_variable_raises(self, workspace: Path):
        template_path = workspace / "templates" / "test-template.md"
        template_path.write_text("Issue: {issue_id}\nTitle: {title}\n")

        with patch("orchestrator.lib.scribe.templates.find_workspace_root", return_value=workspace):
            with pytest.raises(KeyError, match="title"):
                apply_template("test-template.md", {"issue_id": "gt-5"})

    def test_missing_template_raises(self, workspace: Path):
        with patch("orchestrator.lib.scribe.templates.find_workspace_root", return_value=workspace):
            with pytest.raises(FileNotFoundError):
                apply_template("nonexistent.md", {})
