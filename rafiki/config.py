"""Rafiki configuration -- layered: CLI flags > env vars > infra/.env > defaults."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("rafiki.config")


def _load_infra_env(repo_root: Path | None = None) -> dict[str, str]:
    """Parse ``infra/.env`` and return its key-value pairs.

    Does NOT inject the values into ``os.environ`` — callers decide which
    keys to honour.  Lines starting with ``#`` and blank lines are skipped.
    """
    candidates: list[Path] = []
    if repo_root:
        candidates.append(repo_root / "infra" / ".env")
    # Walk up from CWD as fallback
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        candidates.append(parent / "infra" / ".env")
        if (parent / ".git").exists() or (parent / ".beads").exists():
            break

    for env_file in candidates:
        if env_file.is_file():
            pairs: dict[str, str] = {}
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, _, value = line.partition("=")
                # Strip optional surrounding quotes
                value = value.strip().strip("'\"")
                pairs[key.strip()] = value
            logger.debug("Loaded %d vars from %s", len(pairs), env_file)
            return pairs

    return {}


# Module-level cache so the file is read at most once per process.
_infra_env: dict[str, str] | None = None


def _get_infra_env() -> dict[str, str]:
    global _infra_env
    if _infra_env is None:
        _infra_env = _load_infra_env()
    return _infra_env


def _env(rafiki_key: str, *fallback_keys: str, default: str = "") -> str:
    """Look up a config value: RAFIKI_* env var > infra/.env keys > default."""
    val = os.environ.get(rafiki_key)
    if val:
        return val
    infra = _get_infra_env()
    for key in fallback_keys:
        val = infra.get(key)
        if val:
            return val
    return default


@dataclass
class RafikiConfig:
    """Configuration for a Rafiki run."""

    # Connection
    api_url: str = field(
        default_factory=lambda: _env(
            "RAFIKI_API_URL",
            default=f"http://localhost:{_env('RAFIKI_PORT', 'ORCHESTRATOR_PORT', default='9741')}",
        )
    )
    ws_url: str = field(
        default_factory=lambda: _env(
            "RAFIKI_WS_URL",
            default=f"ws://localhost:{_env('RAFIKI_PORT', 'ORCHESTRATOR_PORT', default='9741')}/ws",
        )
    )

    # Project
    project_key: str = field(
        default_factory=lambda: _env("RAFIKI_PROJECT_KEY", default="sci-calc")
    )
    project_name: str = field(
        default_factory=lambda: _env("RAFIKI_PROJECT_NAME", default="Scientific Calculator API")
    )
    project_workspace: str = field(
        default_factory=lambda: _env("RAFIKI_PROJECT_WORKSPACE", "PROJECT_WORKSPACE")
    )

    # Decision engine
    auto_approve: bool = field(
        default_factory=lambda: _env("RAFIKI_AUTO_APPROVE").lower() in ("true", "1", "yes")
    )
    llm_enabled: bool = field(
        default_factory=lambda: _env("RAFIKI_LLM_ENABLED", default="true").lower() in ("true", "1", "yes")
    )
    bedrock_model_id: str = field(
        default_factory=lambda: _env("RAFIKI_BEDROCK_MODEL_ID", "BEDROCK_MODEL_ID", default="us.anthropic.claude-opus-4-6-v1")
    )
    aws_profile: str = field(
        default_factory=lambda: _env("RAFIKI_AWS_PROFILE", "AWS_PROFILE", default="ai3_d")
    )

    # Timing
    poll_interval: float = field(
        default_factory=lambda: float(_env("RAFIKI_POLL_INTERVAL", default="5.0"))
    )
    stall_threshold: float = field(
        default_factory=lambda: float(_env("RAFIKI_STALL_THRESHOLD", default="300.0"))
    )
    max_stalls: int = field(
        default_factory=lambda: int(_env("RAFIKI_MAX_STALLS", default="5"))
    )
    max_runtime: float = field(
        default_factory=lambda: float(_env("RAFIKI_MAX_RUNTIME", default="7200.0"))
    )
    completion_timeout: float = field(
        default_factory=lambda: float(_env("RAFIKI_COMPLETION_TIMEOUT", default="120.0"))
    )

    # Cleanup
    skip_cleanup: bool = field(
        default_factory=lambda: _env("RAFIKI_SKIP_CLEANUP").lower() in ("true", "1", "yes")
    )
    cleanup_timeout: float = field(
        default_factory=lambda: float(_env("RAFIKI_CLEANUP_TIMEOUT", default="60.0"))
    )
    preserve_artifacts: bool = field(
        default_factory=lambda: _env("RAFIKI_PRESERVE_ARTIFACTS").lower() in ("true", "1", "yes")
    )

    # Paths
    state_file: str = field(
        default_factory=lambda: _env("RAFIKI_STATE_FILE", default="rafiki-state.json")
    )
    report_file: str = field(
        default_factory=lambda: _env("RAFIKI_REPORT_FILE", default="rafiki-report.json")
    )
    log_file: str | None = field(
        default_factory=lambda: os.environ.get("RAFIKI_LOG_FILE")
    )

    # Docker path mapping (host → container)
    docker_workspace_root: str = field(
        default_factory=lambda: _env("RAFIKI_DOCKER_WORKSPACE_ROOT", "GORILLA_WORKSPACE", default="/workspace")
    )
    host_workspace_root: str = field(
        default_factory=lambda: _env("RAFIKI_HOST_WORKSPACE_ROOT", "PROJECT_WORKSPACE")
    )

    # Logging
    log_level: str = field(
        default_factory=lambda: _env("RAFIKI_LOG_LEVEL", "GORILLA_LOG_LEVEL", default="INFO")
    )
    log_format: str = field(
        default_factory=lambda: _env("RAFIKI_LOG_FORMAT", default="text")
    )

    def resolve_workspace(self, repo_root: Path) -> Path:
        """Resolve the project workspace path (local host path).

        Priority:
            1. Explicit ``project_workspace`` (from RAFIKI_PROJECT_WORKSPACE
               or PROJECT_WORKSPACE in infra/.env)
            2. Fallback: ``repo_root / "rafiki-project"``

        When ``project_workspace`` comes from the infra ``.env`` file it
        points to the volume-mount source (e.g.
        ``C:/dev/git-repos/aidlc-beads/workspace``).  The project-specific
        workspace is a subdirectory named after the project key.
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
            if relative:
                return f"{self.docker_workspace_root.rstrip('/')}/{relative}"
            return self.docker_workspace_root.rstrip("/")
        return str(local_path)
