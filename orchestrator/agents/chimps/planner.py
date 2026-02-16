"""Planner -- plans workflows and generates construction units from design artifacts."""

from __future__ import annotations

from orchestrator.agents.chimps.base_chimp import BaseChimp


class Planner(BaseChimp):
    """Creates workflow plans and breaks down design into executable construction units.

    Handles workflow-planning (determine which stages to execute vs skip,
    create execution plan, wire Beads dependencies) and units-generation
    (decompose system into construction units with boundaries).
    """

    agent_type = "Planner"
    agent_mail_identity = "Planner"
    handled_stages = ["workflow-planning", "units-generation"]

    tool_names = [
        "read_artifact",
        "scribe_create_artifact",
        "beads_list_issues",
        "beads_create_issue",
        "beads_add_dependency",
    ]
