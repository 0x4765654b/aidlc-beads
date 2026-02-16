"""Scribe Tool Library -- Artifact management for Gorilla Troop agents.

Scribe provides deterministic functions for creating, validating, registering,
and syncing AIDLC artifacts. All Chimp agents use Scribe. No LLM dependency.
"""

from orchestrator.lib.scribe.headers import parse_header, write_header, strip_header
from orchestrator.lib.scribe.artifacts import (
    create_artifact,
    update_artifact,
    validate_artifact,
    register_artifact,
    list_stage_artifacts,
)
from orchestrator.lib.scribe.outline_sync import (
    sync_to_outline,
    pull_from_outline,
    outline_sync_status,
)
from orchestrator.lib.scribe.templates import apply_template
from orchestrator.lib.scribe.models import ArtifactHeader, ValidationResult, ArtifactInfo
from orchestrator.lib.scribe.workspace import find_workspace_root

__all__ = [
    "parse_header",
    "write_header",
    "strip_header",
    "create_artifact",
    "update_artifact",
    "validate_artifact",
    "register_artifact",
    "list_stage_artifacts",
    "sync_to_outline",
    "pull_from_outline",
    "outline_sync_status",
    "apply_template",
    "find_workspace_root",
    "ArtifactHeader",
    "ValidationResult",
    "ArtifactInfo",
]
