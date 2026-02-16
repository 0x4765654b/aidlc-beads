"""Architect -- designs application structure and infrastructure topology."""

from __future__ import annotations

from orchestrator.agents.chimps.base_chimp import BaseChimp


class Architect(BaseChimp):
    """Produces application architecture and infrastructure design documents.

    Handles application-design (high-level component identification,
    interfaces, data flows, service boundaries) and infrastructure-design
    (map components to AWS services, networking, security, scaling).
    """

    agent_type = "Architect"
    agent_mail_identity = "Architect"
    handled_stages = ["application-design", "infrastructure-design"]

    tool_names = [
        "read_artifact",
        "scribe_create_artifact",
        "read_file",
        "list_directory",
    ]
