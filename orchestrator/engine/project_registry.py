"""Project Registry -- multi-project state management."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("engine.project_registry")

REGISTRY_DIR = ".gorilla-troop"
REGISTRY_FILE = "projects.json"


@dataclass
class ProjectState:
    """State of a single AIDLC project."""

    project_key: str
    name: str
    workspace_path: str
    status: str = "active"  # active, paused, completed
    minder_agent_id: str | None = None
    created_at: str = ""
    paused_at: str | None = None


class ProjectRegistry:
    """Manages multiple AIDLC projects with persistent state.

    State is persisted to {workspace}/.gorilla-troop/projects.json.
    """

    def __init__(self, workspace_root: Path | None = None) -> None:
        self._root = workspace_root or Path.cwd()
        self._projects: dict[str, ProjectState] = {}
        self._load()

    def _registry_path(self) -> Path:
        return self._root / REGISTRY_DIR / REGISTRY_FILE

    def _load(self) -> None:
        """Load project state from disk."""
        path = self._registry_path()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                for key, proj_data in data.items():
                    self._projects[key] = ProjectState(**proj_data)
                logger.info("Loaded %d projects from registry", len(self._projects))
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning("Failed to load project registry: %s", e)

    def _save(self) -> None:
        """Save project state to disk atomically."""
        path = self._registry_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        data = {k: asdict(v) for k, v in self._projects.items()}
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(path)

    def create_project(self, key: str, name: str, workspace_path: str) -> ProjectState:
        """Register a new project.

        Args:
            key: Unique project key (e.g., "gorilla-troop").
            name: Human-readable project name.
            workspace_path: Path to project workspace.

        Returns:
            The created ProjectState.

        Raises:
            ValueError: If project key already exists.
        """
        if key in self._projects:
            raise ValueError(f"Project '{key}' already exists")

        project = ProjectState(
            project_key=key,
            name=name,
            workspace_path=workspace_path,
            status="active",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._projects[key] = project
        self._save()
        logger.info("Created project: %s (%s)", key, name)
        return project

    def get_project(self, key: str) -> ProjectState | None:
        """Get project by key."""
        return self._projects.get(key)

    def list_projects(self, status: str | None = None) -> list[ProjectState]:
        """List all projects, optionally filtered by status."""
        projects = list(self._projects.values())
        if status:
            projects = [p for p in projects if p.status == status]
        return sorted(projects, key=lambda p: p.project_key)

    def pause_project(self, key: str) -> None:
        """Pause a project.

        Raises:
            KeyError: If project not found.
        """
        project = self._projects.get(key)
        if not project:
            raise KeyError(f"Project '{key}' not found")
        project.status = "paused"
        project.paused_at = datetime.now(timezone.utc).isoformat()
        self._save()
        logger.info("Paused project: %s", key)

    def resume_project(self, key: str) -> None:
        """Resume a paused project.

        Raises:
            KeyError: If project not found.
        """
        project = self._projects.get(key)
        if not project:
            raise KeyError(f"Project '{key}' not found")
        project.status = "active"
        project.paused_at = None
        self._save()
        logger.info("Resumed project: %s", key)

    def update_project(self, key: str, **kwargs) -> None:
        """Update project fields.

        Raises:
            KeyError: If project not found.
        """
        project = self._projects.get(key)
        if not project:
            raise KeyError(f"Project '{key}' not found")
        for field_name, value in kwargs.items():
            if hasattr(project, field_name):
                setattr(project, field_name, value)
        self._save()

    def delete_project(self, key: str) -> None:
        """Remove a project from the registry.

        Raises:
            KeyError: If project not found.
        """
        if key not in self._projects:
            raise KeyError(f"Project '{key}' not found")
        del self._projects[key]
        self._save()
        logger.info("Deleted project: %s", key)
