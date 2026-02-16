"""Sage -- analyzes requirements and produces functional design specifications."""

from __future__ import annotations

from orchestrator.agents.chimps.base_chimp import BaseChimp


class Sage(BaseChimp):
    """Analyzes stakeholder needs and produces requirements documents and functional design specs.

    Handles requirements-analysis (gather requirements, generate clarifying
    questions, produce requirements document) and functional-design (create
    detailed functional specs with interfaces, data models, business rules).
    """

    agent_type = "Sage"
    agent_mail_identity = "Sage"
    handled_stages = ["requirements-analysis", "functional-design"]

    tool_names = [
        "read_artifact",
        "scribe_create_artifact",
        "scribe_update_artifact",
        "search_beads_history",
        "scribe_list_artifacts",
    ]
