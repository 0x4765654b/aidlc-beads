"""Tool permission registry -- which agents can use which tools."""

from __future__ import annotations


# Maps agent type -> list of tool names they are authorized to use
AGENT_TOOL_REGISTRY: dict[str, list[str]] = {
    # Chimps
    "Scout": [
        "read_file", "list_directory", "search_code",
        "scribe_create_artifact", "scribe_validate", "scribe_list_artifacts",
    ],
    "Sage": [
        "read_artifact", "scribe_create_artifact", "scribe_update_artifact",
        "search_beads_history", "scribe_list_artifacts",
    ],
    "Bard": [
        "read_artifact", "scribe_create_artifact", "search_prior_artifacts",
    ],
    "Planner": [
        "read_artifact", "scribe_create_artifact",
        "beads_list_issues", "beads_create_issue", "beads_add_dependency",
    ],
    "Architect": [
        "read_artifact", "scribe_create_artifact", "read_file", "list_directory",
    ],
    "Steward": [
        "read_artifact", "scribe_create_artifact", "search_prior_artifacts",
    ],
    "Forge": [
        "read_artifact", "read_file", "write_code_file", "git_commit", "run_linter",
    ],
    "Crucible": [
        "read_artifact", "read_file", "write_test_file", "run_tests", "run_linter", "git_commit",
    ],

    # Cross-cutting
    "Harmbe": [
        "project_create", "project_list", "project_status",
        "project_pause", "project_resume",
        "approve_review", "reject_review", "answer_qa",
        "approve_skip", "deny_skip",
        "get_notifications", "search_history",
    ],
    "ProjectMinder": [
        "dispatch_stage", "check_ready", "check_blocked",
        "create_review_gate", "recommend_skip",
        "update_stage_status", "file_reservation",
    ],
    "Bonobo": [
        "write_file", "delete_file",
        "git_commit", "git_create_branch", "git_checkout", "git_merge",
        "beads_create", "beads_update", "beads_close",
        "outline_push", "outline_pull",
    ],
    "Groomer": [
        "check_inbox", "compile_status_report",
        "detect_stale", "notify_harmbe",
    ],
    "Snake": [
        "scan_artifact", "scan_code", "scan_dependencies",
        "generate_security_report",
    ],
    "CuriousGeorge": [
        "read_file", "read_beads_issue", "read_agent_mail_thread",
        "attempt_fix", "escalate",
    ],
    "Gibbon": [
        "read_artifact", "read_review_feedback",
        "scribe_create_artifact", "scribe_update_artifact",
        "write_code_file", "run_tests",
    ],
    "Troop": [
        "read_file", "read_artifact", "write_file",
        "scribe_create_artifact", "scribe_update_artifact",
        "beads_list_issues",
    ],
}


class ToolGuard:
    """Enforces tool access permissions per agent role."""

    def validate_tool_access(self, agent_type: str, tool_name: str) -> bool:
        """Check if an agent type is allowed to use a tool.

        Args:
            agent_type: The agent role name (e.g., "Scout").
            tool_name: The tool being requested.

        Returns:
            True if allowed, False if denied.
        """
        allowed = AGENT_TOOL_REGISTRY.get(agent_type, [])
        return tool_name in allowed

    def get_allowed_tools(self, agent_type: str) -> list[str]:
        """Get the list of tools an agent is allowed to use.

        Args:
            agent_type: The agent role name.

        Returns:
            List of allowed tool names.
        """
        return list(AGENT_TOOL_REGISTRY.get(agent_type, []))
