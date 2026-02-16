"""Crucible -- runs builds and tests to validate generated code."""

from __future__ import annotations

from orchestrator.agents.chimps.base_chimp import BaseChimp


class Crucible(BaseChimp):
    """Executes builds and test suites to validate code quality and correctness.

    Handles build-and-test: validates code quality and correctness by
    running builds, writing tests, executing test suites, and producing
    test reports and build logs.
    """

    agent_type = "Crucible"
    agent_mail_identity = "Crucible"
    handled_stages = ["build-and-test"]

    tool_names = [
        "read_artifact",
        "read_file",
        "write_test_file",
        "run_tests",
        "run_linter",
        "git_commit",
    ]
