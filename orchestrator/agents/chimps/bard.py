"""Bard -- crafts user stories from requirements and stakeholder input."""

from __future__ import annotations

from orchestrator.agents.chimps.base_chimp import BaseChimp


class Bard(BaseChimp):
    """Transforms requirements into well-formed user stories with acceptance criteria.

    Handles user-stories: creates user personas, epics, and detailed stories
    with Given-When-Then acceptance criteria.
    """

    agent_type = "Bard"
    agent_mail_identity = "Bard"
    handled_stages = ["user-stories"]

    tool_names = [
        "read_artifact",
        "scribe_create_artifact",
        "search_prior_artifacts",
    ]
