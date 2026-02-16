"""Context Dispatch Protocol -- standardized message format for agent delegation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict

# Stage name -> default agent type
STAGE_AGENT_MAP: dict[str, str] = {
    # Inception
    "workspace-detection": "Scout",
    "reverse-engineering": "Scout",
    "requirements-analysis": "Sage",
    "user-stories": "Bard",
    "workflow-planning": "Planner",
    "application-design": "Architect",
    "units-generation": "Planner",
    # Construction
    "functional-design": "Sage",
    "nfr-requirements": "Steward",
    "nfr-design": "Steward",
    "infrastructure-design": "Architect",
    "code-generation": "Forge",
    "build-and-test": "Crucible",
}


@dataclass
class DispatchMessage:
    """Message sent from Project Minder to a Chimp to execute a stage."""

    stage_name: str
    stage_type: str
    beads_issue_id: str
    review_gate_id: str | None = None
    unit_name: str | None = None
    phase: str = "inception"

    # Context artifacts to load
    input_artifacts: list[str] = field(default_factory=list)
    reference_docs: list[str] = field(default_factory=list)

    # Execution parameters
    project_key: str = ""
    workspace_root: str = ""

    # Agent assignment
    assigned_agent: str = ""

    # Optional overrides
    instructions: str | None = None


@dataclass
class CompletionMessage:
    """Message sent from a Chimp back to Project Minder after completing a stage."""

    stage_name: str
    beads_issue_id: str
    status: str  # "completed", "failed", "needs_rework"

    # Output
    output_artifacts: list[str] = field(default_factory=list)
    summary: str = ""

    # Discovered work
    discovered_issues: list[dict] = field(default_factory=list)

    # Error info
    error_detail: str | None = None
    rework_reason: str | None = None


def build_dispatch(
    stage_name: str,
    beads_issue_id: str,
    project_key: str,
    workspace_root: str,
    *,
    stage_type: str | None = None,
    review_gate_id: str | None = None,
    unit_name: str | None = None,
    phase: str = "inception",
    input_artifacts: list[str] | None = None,
    reference_docs: list[str] | None = None,
    assigned_agent: str | None = None,
    instructions: str | None = None,
) -> DispatchMessage:
    """Factory function to construct a DispatchMessage with smart defaults.

    Args:
        stage_name: The AIDLC stage name.
        beads_issue_id: Beads issue for this stage.
        project_key: Agent Mail project key.
        workspace_root: Path to workspace.
        stage_type: Override stage type (defaults to stage_name).
        review_gate_id: Review gate issue ID.
        unit_name: Construction unit name.
        phase: "inception" or "construction".
        input_artifacts: Artifacts to load.
        reference_docs: Additional reference docs.
        assigned_agent: Override agent assignment.
        instructions: Additional instructions.

    Returns:
        Fully populated DispatchMessage.
    """
    effective_stage_type = stage_type or stage_name
    effective_agent = assigned_agent or STAGE_AGENT_MAP.get(effective_stage_type, "Troop")

    return DispatchMessage(
        stage_name=stage_name,
        stage_type=effective_stage_type,
        beads_issue_id=beads_issue_id,
        review_gate_id=review_gate_id,
        unit_name=unit_name,
        phase=phase,
        input_artifacts=input_artifacts or [],
        reference_docs=reference_docs or [],
        project_key=project_key,
        workspace_root=workspace_root,
        assigned_agent=effective_agent,
        instructions=instructions,
    )


def build_completion(
    stage_name: str,
    beads_issue_id: str,
    output_artifacts: list[str],
    summary: str,
    *,
    status: str = "completed",
    discovered_issues: list[dict] | None = None,
    error_detail: str | None = None,
    rework_reason: str | None = None,
) -> CompletionMessage:
    """Factory function to construct a CompletionMessage.

    Returns:
        Fully populated CompletionMessage.
    """
    return CompletionMessage(
        stage_name=stage_name,
        beads_issue_id=beads_issue_id,
        status=status,
        output_artifacts=output_artifacts,
        summary=summary,
        discovered_issues=discovered_issues or [],
        error_detail=error_detail,
        rework_reason=rework_reason,
    )


def serialize_dispatch(msg: DispatchMessage) -> str:
    """Serialize a DispatchMessage to JSON string."""
    return json.dumps(asdict(msg), indent=2)


def deserialize_dispatch(data: str) -> DispatchMessage:
    """Deserialize a DispatchMessage from JSON string."""
    d = json.loads(data)
    return DispatchMessage(**d)


def serialize_completion(msg: CompletionMessage) -> str:
    """Serialize a CompletionMessage to JSON string."""
    return json.dumps(asdict(msg), indent=2)


def deserialize_completion(data: str) -> CompletionMessage:
    """Deserialize a CompletionMessage from JSON string."""
    d = json.loads(data)
    return CompletionMessage(**d)
