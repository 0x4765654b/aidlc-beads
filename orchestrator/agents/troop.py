"""Troop -- general purpose short-lived worker agent."""

from __future__ import annotations

import uuid

from orchestrator.agents.base import BaseAgent


class Troop(BaseAgent):
    """General purpose worker spawned for ad-hoc tasks.

    Short-lived: created for a specific task, executes it, then stops.
    Use cases: discovered work, one-off research, parallel subtasks.

    Each Troop instance gets a unique identity: Troop-{uuid8}.
    """

    agent_type = "Troop"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Each troop worker gets a unique identity
        self.agent_mail_identity = f"Troop-{uuid.uuid4().hex[:8]}"
