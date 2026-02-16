"""Tests for app factory auto-registration of default project."""

from __future__ import annotations

from pathlib import Path

import pytest

from orchestrator.api.app import create_app
from orchestrator.config import reset_config
from orchestrator.engine.project_registry import ProjectRegistry
from orchestrator.engine.agent_engine import AgentEngine
from orchestrator.engine.notification_manager import NotificationManager


@pytest.fixture(autouse=True)
def _clean_config():
    """Reset the global config singleton before and after each test."""
    reset_config()
    yield
    reset_config()


@pytest.fixture
def tmp_registry(tmp_path: Path) -> ProjectRegistry:
    """Create a ProjectRegistry backed by a temp directory."""
    return ProjectRegistry(workspace_root=tmp_path)


def _make_app(registry: ProjectRegistry) -> object:
    return create_app(
        project_registry=registry,
        agent_engine=AgentEngine(),
        notification_manager=NotificationManager(),
    )


class TestDefaultProjectAutoRegistration:
    """Test auto-registration of a default project on app startup."""

    @pytest.mark.asyncio
    async def test_auto_registers_when_env_vars_set(
        self, tmp_path: Path, tmp_registry: ProjectRegistry, monkeypatch
    ):
        """When DEFAULT_PROJECT_KEY and DEFAULT_PROJECT_PATH point to a real
        directory, the project is registered automatically on startup."""
        project_dir = tmp_path / "my-project"
        project_dir.mkdir()

        monkeypatch.setenv("DEFAULT_PROJECT_KEY", "test-proj")
        monkeypatch.setenv("DEFAULT_PROJECT_NAME", "Test Project")
        monkeypatch.setenv("DEFAULT_PROJECT_PATH", str(project_dir))

        app = _make_app(tmp_registry)

        # Explicitly trigger the ASGI lifespan (ASGITransport does not)
        async with app.router.lifespan_context(app):
            project = tmp_registry.get_project("test-proj")
            assert project is not None
            assert project.name == "Test Project"
            assert project.workspace_path == str(project_dir)

    @pytest.mark.asyncio
    async def test_no_registration_when_env_vars_empty(
        self, tmp_registry: ProjectRegistry, monkeypatch
    ):
        """When DEFAULT_PROJECT_KEY is empty, no project is auto-registered."""
        monkeypatch.setenv("DEFAULT_PROJECT_KEY", "")
        monkeypatch.setenv("DEFAULT_PROJECT_PATH", "")

        app = _make_app(tmp_registry)

        async with app.router.lifespan_context(app):
            assert tmp_registry.list_projects() == []

    @pytest.mark.asyncio
    async def test_idempotent_when_project_already_exists(
        self, tmp_path: Path, tmp_registry: ProjectRegistry, monkeypatch
    ):
        """If the project is already registered, startup does not fail or
        create a duplicate."""
        project_dir = tmp_path / "existing"
        project_dir.mkdir()

        # Pre-register the project
        tmp_registry.create_project("existing-proj", "Existing", str(project_dir))

        monkeypatch.setenv("DEFAULT_PROJECT_KEY", "existing-proj")
        monkeypatch.setenv("DEFAULT_PROJECT_NAME", "Existing")
        monkeypatch.setenv("DEFAULT_PROJECT_PATH", str(project_dir))

        app = _make_app(tmp_registry)

        async with app.router.lifespan_context(app):
            # Still exactly one project
            projects = tmp_registry.list_projects()
            assert len(projects) == 1
            assert projects[0].project_key == "existing-proj"
