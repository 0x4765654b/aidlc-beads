"""Scout -- explores the workspace and reverse-engineers existing codebases."""

from __future__ import annotations

from orchestrator.agents.chimps.base_chimp import BaseChimp


class Scout(BaseChimp):
    """Explores the project workspace and reverse-engineers existing code to produce discovery artifacts.

    Handles workspace-detection (scan filesystem, identify project type,
    languages, build systems) and reverse-engineering (analyze brownfield
    codebases to document architecture, components, tech stack).
    """

    agent_type = "Scout"
    agent_mail_identity = "Scout"
    handled_stages = ["workspace-detection", "reverse-engineering"]

    # Tools exposed to the Strands agent loop
    tool_names = [
        "read_file",
        "list_directory",
        "search_code",
        "scribe_create_artifact",
        "scribe_validate",
        "scribe_list_artifacts",
    ]
