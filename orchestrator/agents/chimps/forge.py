"""Forge -- generates implementation code from design and unit specifications."""

from __future__ import annotations

from orchestrator.agents.chimps.base_chimp import BaseChimp


class Forge(BaseChimp):
    """Generates production code from functional design, units, and architecture artifacts.

    Handles code-generation: translates functional design, architecture, and
    NFR design artifacts into production implementation code. Writes code via
    Bonobo FileGuard and commits via Bonobo GitGuard.
    """

    agent_type = "Forge"
    agent_mail_identity = "Forge"
    handled_stages = ["code-generation"]

    tool_names = [
        "read_artifact",
        "read_file",
        "write_code_file",
        "git_commit",
        "run_linter",
    ]
