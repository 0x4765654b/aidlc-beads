"""Steward -- captures and designs non-functional requirements and their solutions."""

from __future__ import annotations

from orchestrator.agents.chimps.base_chimp import BaseChimp


class Steward(BaseChimp):
    """Identifies NFRs (security, performance, observability) and produces NFR design artifacts.

    Handles nfr-requirements (identify and catalog security, performance,
    observability, reliability requirements) and nfr-design (design solutions
    for each NFR with specific technologies and patterns).
    """

    agent_type = "Steward"
    agent_mail_identity = "Steward"
    handled_stages = ["nfr-requirements", "nfr-design"]

    tool_names = [
        "read_artifact",
        "scribe_create_artifact",
        "search_prior_artifacts",
    ]
