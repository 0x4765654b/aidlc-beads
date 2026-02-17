"""Rafiki configuration -- layered: CLI flags > env vars > YAML > defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RafikiConfig:
    """Configuration for a Rafiki run."""

    # Connection
    api_url: str = field(
        default_factory=lambda: os.environ.get("RAFIKI_API_URL", "http://localhost:9741")
    )
    ws_url: str = field(
        default_factory=lambda: os.environ.get("RAFIKI_WS_URL", "ws://localhost:9741/ws")
    )

    # Project
    project_key: str = field(
        default_factory=lambda: os.environ.get("RAFIKI_PROJECT_KEY", "sci-calc")
    )
    project_name: str = field(
        default_factory=lambda: os.environ.get("RAFIKI_PROJECT_NAME", "Scientific Calculator API")
    )
    project_workspace: str = field(
        default_factory=lambda: os.environ.get("RAFIKI_PROJECT_WORKSPACE", "")
    )

    # Decision engine
    auto_approve: bool = field(
        default_factory=lambda: os.environ.get("RAFIKI_AUTO_APPROVE", "").lower() in ("true", "1", "yes")
    )
    llm_enabled: bool = field(
        default_factory=lambda: os.environ.get("RAFIKI_LLM_ENABLED", "true").lower() in ("true", "1", "yes")
    )
    bedrock_model_id: str = field(
        default_factory=lambda: os.environ.get("RAFIKI_BEDROCK_MODEL_ID", "us.anthropic.claude-opus-4-6-v1")
    )
    aws_profile: str = field(
        default_factory=lambda: os.environ.get("RAFIKI_AWS_PROFILE", "ai3_d")
    )

    # Timing
    poll_interval: float = field(
        default_factory=lambda: float(os.environ.get("RAFIKI_POLL_INTERVAL", "5.0"))
    )
    stall_threshold: float = field(
        default_factory=lambda: float(os.environ.get("RAFIKI_STALL_THRESHOLD", "300.0"))
    )
    max_stalls: int = field(
        default_factory=lambda: int(os.environ.get("RAFIKI_MAX_STALLS", "5"))
    )
    max_runtime: float = field(
        default_factory=lambda: float(os.environ.get("RAFIKI_MAX_RUNTIME", "7200.0"))
    )
    completion_timeout: float = field(
        default_factory=lambda: float(os.environ.get("RAFIKI_COMPLETION_TIMEOUT", "120.0"))
    )

    # Cleanup
    skip_cleanup: bool = field(
        default_factory=lambda: os.environ.get("RAFIKI_SKIP_CLEANUP", "").lower() in ("true", "1", "yes")
    )
    cleanup_timeout: float = field(
        default_factory=lambda: float(os.environ.get("RAFIKI_CLEANUP_TIMEOUT", "60.0"))
    )
    preserve_artifacts: bool = field(
        default_factory=lambda: os.environ.get("RAFIKI_PRESERVE_ARTIFACTS", "").lower() in ("true", "1", "yes")
    )

    # Paths
    state_file: str = field(
        default_factory=lambda: os.environ.get("RAFIKI_STATE_FILE", "rafiki-state.json")
    )
    report_file: str = field(
        default_factory=lambda: os.environ.get("RAFIKI_REPORT_FILE", "rafiki-report.json")
    )
    log_file: str | None = field(
        default_factory=lambda: os.environ.get("RAFIKI_LOG_FILE")
    )

    # Docker path mapping (host → container)
    docker_workspace_root: str = field(
        default_factory=lambda: os.environ.get("RAFIKI_DOCKER_WORKSPACE_ROOT", "/workspace")
    )
    host_workspace_root: str = field(
        default_factory=lambda: os.environ.get("RAFIKI_HOST_WORKSPACE_ROOT", "")
    )

    # Logging
    log_level: str = field(
        default_factory=lambda: os.environ.get("RAFIKI_LOG_LEVEL", "INFO")
    )
    log_format: str = field(
        default_factory=lambda: os.environ.get("RAFIKI_LOG_FORMAT", "text")
    )

    def resolve_workspace(self, repo_root: Path) -> Path:
        """Resolve the project workspace path (local host path).

        If project_workspace is set, use it. Otherwise, derive from
        the rafiki-project/ directory relative to the repo root.
        """
        if self.project_workspace:
            return Path(self.project_workspace)
        return repo_root / "rafiki-project"

    def resolve_docker_workspace(self, local_path: Path) -> str:
        """Translate a local host path to the Docker-internal path.

        Uses host_workspace_root and docker_workspace_root to map paths.
        If host_workspace_root is not set, returns the local path as-is.
        """
        if not self.host_workspace_root:
            return str(local_path)
        local_str = str(local_path.resolve()).replace("\\", "/")
        host_str = self.host_workspace_root.replace("\\", "/")
        if local_str.startswith(host_str):
            relative = local_str[len(host_str):].lstrip("/")
            return f"{self.docker_workspace_root.rstrip('/')}/{relative}"
        return str(local_path)
