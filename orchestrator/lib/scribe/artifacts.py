"""Core artifact management functions."""

from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from orchestrator.lib.scribe.headers import parse_header, write_header, strip_header
from orchestrator.lib.scribe.models import ArtifactHeader, ArtifactInfo, ValidationResult
from orchestrator.lib.scribe.workspace import find_workspace_root, AIDLC_DOCS_DIR

# Valid characters for stage and file names
_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9\-]*$")


def _validate_name(name: str, kind: str) -> None:
    """Validate that a stage or file name uses allowed characters."""
    if not _NAME_PATTERN.match(name):
        raise ValueError(
            f"Invalid {kind} name '{name}'. "
            f"Must be lowercase alphanumeric with hyphens (e.g., 'functional-design')."
        )


def create_artifact(
    stage: str,
    name: str,
    content: str,
    beads_issue_id: str,
    review_gate_id: str | None = None,
    phase: str = "inception",
) -> Path:
    """Create a markdown artifact file with correct headers and directory placement.

    Args:
        stage: Directory name (e.g., "reverse-engineering", "unit-1-scribe").
        name: File name without extension (e.g., "architecture").
        content: Markdown body (without headers -- headers are prepended).
        beads_issue_id: Issue ID for the beads-issue header.
        review_gate_id: Optional review gate ID for the beads-review header.
        phase: "inception" or "construction" (default "inception").

    Returns:
        Absolute path to the created file.

    Raises:
        FileExistsError: If the file already exists.
        ValueError: If stage or name contains invalid characters.
    """
    _validate_name(stage, "stage")
    _validate_name(name, "file")

    if phase not in ("inception", "construction"):
        raise ValueError(f"Invalid phase '{phase}'. Must be 'inception' or 'construction'.")

    root = find_workspace_root()
    artifact_dir = root / AIDLC_DOCS_DIR / phase / stage
    artifact_path = artifact_dir / f"{name}.md"

    if artifact_path.exists():
        raise FileExistsError(f"Artifact already exists: {artifact_path}")

    # Create directory structure
    artifact_dir.mkdir(parents=True, exist_ok=True)

    # Build content with headers
    header = write_header(beads_issue_id, review_gate_id)
    full_content = header + content

    artifact_path.write_text(full_content, encoding="utf-8")
    return artifact_path


def update_artifact(path: Path, content: str) -> Path:
    """Update an existing artifact's body content while preserving its headers.

    Args:
        path: Path to the existing artifact.
        content: New markdown body (without headers).

    Returns:
        Path to the updated file.

    Raises:
        FileNotFoundError: If the file doesn't exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Artifact not found: {path}")

    existing_content = path.read_text(encoding="utf-8")
    header_obj = parse_header(existing_content)
    header = write_header(header_obj.beads_issue, header_obj.beads_review)
    full_content = header + content

    path.write_text(full_content, encoding="utf-8")
    return path


def validate_artifact(path: Path) -> ValidationResult:
    """Validate an artifact file for correctness.

    Checks: file exists, has beads-issue header, has H1 heading,
    path matches directory structure, file is not empty.

    Args:
        path: Path to the artifact file.

    Returns:
        ValidationResult with valid flag, errors, and warnings.
    """
    path = Path(path)
    errors: list[str] = []
    warnings: list[str] = []

    # Check file exists
    if not path.exists():
        return ValidationResult(valid=False, errors=["File does not exist"], path=path)

    if not path.is_file():
        return ValidationResult(valid=False, errors=["Path is not a file"], path=path)

    content = path.read_text(encoding="utf-8")

    # Check not empty
    if not content.strip():
        return ValidationResult(valid=False, errors=["File is empty"], path=path)

    # Check beads-issue header
    try:
        header = parse_header(content)
    except ValueError as e:
        errors.append(str(e))
        header = None

    # Check beads-review header (warning, not error)
    if header and not header.beads_review:
        warnings.append("beads-review header is missing (optional for non-reviewed artifacts)")

    # Check for H1 heading
    body = strip_header(content) if header else content
    if not re.search(r"^#\s+.+", body, re.MULTILINE):
        errors.append("No H1 heading found (expected '# Title' in the document)")

    # Check directory structure
    try:
        root = find_workspace_root(path.parent)
        relative = path.relative_to(root)
        parts = relative.parts
        if len(parts) < 3 or parts[0] != AIDLC_DOCS_DIR:
            warnings.append(
                f"Path does not follow aidlc-docs/{{phase}}/{{stage}}/ convention: {relative}"
            )
        elif parts[1] not in ("inception", "construction"):
            warnings.append(f"Phase directory '{parts[1]}' is not 'inception' or 'construction'")
    except RuntimeError:
        warnings.append("Could not determine workspace root for path validation")

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        path=path,
    )


def register_artifact(beads_issue_id: str, artifact_path: Path) -> None:
    """Update the Beads issue notes field with artifact: <path>.

    Args:
        beads_issue_id: The Beads issue ID to update.
        artifact_path: Path to the artifact (stored as relative to workspace root).

    Raises:
        subprocess.CalledProcessError: If the bd command fails.
    """
    # Make path relative to workspace root
    try:
        root = find_workspace_root()
        relative_path = Path(artifact_path).relative_to(root)
    except (RuntimeError, ValueError):
        relative_path = Path(artifact_path)

    subprocess.run(
        ["bd", "update", beads_issue_id, "--append-notes", f"artifact: {relative_path}"],
        check=True,
        capture_output=True,
        text=True,
    )


def list_stage_artifacts(stage_name: str, phase: str = "inception") -> list[ArtifactInfo]:
    """List all artifacts in a stage directory with metadata.

    Args:
        stage_name: Directory name of the stage.
        phase: "inception" or "construction".

    Returns:
        List of ArtifactInfo sorted by filename. Empty list if directory doesn't exist.
    """
    root = find_workspace_root()
    stage_dir = root / AIDLC_DOCS_DIR / phase / stage_name

    if not stage_dir.is_dir():
        return []

    artifacts: list[ArtifactInfo] = []

    for md_file in sorted(stage_dir.glob("*.md")):
        try:
            content = md_file.read_text(encoding="utf-8")
            header = parse_header(content)
            body = strip_header(content)

            # Extract first H1 heading as title
            title_match = re.search(r"^#\s+(.+)", body, re.MULTILINE)
            title = title_match.group(1).strip() if title_match else "(untitled)"

            stat = md_file.stat()

            artifacts.append(
                ArtifactInfo(
                    path=md_file,
                    header=header,
                    title=title,
                    stage=stage_name,
                    phase=phase,
                    size_bytes=stat.st_size,
                    last_modified=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                )
            )
        except (ValueError, OSError):
            # Skip files that can't be parsed (e.g., missing headers)
            continue

    return artifacts
