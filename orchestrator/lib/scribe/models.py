"""Data models for the Scribe tool library."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class ArtifactHeader:
    """Parsed cross-reference header from a markdown artifact."""

    beads_issue: str
    beads_review: str | None = None


@dataclass
class ValidationResult:
    """Result of artifact validation."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    path: Path = field(default_factory=lambda: Path("."))


@dataclass
class ArtifactInfo:
    """Metadata about an artifact file."""

    path: Path
    header: ArtifactHeader
    title: str
    stage: str
    phase: str
    size_bytes: int
    last_modified: datetime
