"""Tests for Unit 9: Docker Infrastructure configuration validation."""

from __future__ import annotations

from pathlib import Path

import pytest

# Path to the infra directory
INFRA_DIR = Path(__file__).resolve().parents[2] / "infra"


class TestDockerComposeExists:
    def test_compose_file_exists(self):
        assert (INFRA_DIR / "docker-compose.yml").exists()

    def test_compose_dev_file_exists(self):
        assert (INFRA_DIR / "docker-compose.dev.yml").exists()

    def test_dockerfile_orchestrator_exists(self):
        assert (INFRA_DIR / "Dockerfile.orchestrator").exists()

    def test_dockerfile_dashboard_exists(self):
        assert (INFRA_DIR / "Dockerfile.dashboard").exists()

    def test_nginx_conf_exists(self):
        assert (INFRA_DIR / "nginx.conf").exists()

    def test_env_example_exists(self):
        assert (INFRA_DIR / ".env.example").exists()


class TestDockerComposeContent:
    @pytest.fixture
    def compose(self) -> str:
        return (INFRA_DIR / "docker-compose.yml").read_text(encoding="utf-8")

    def test_has_orchestrator_service(self, compose):
        assert "orchestrator:" in compose

    def test_has_dashboard_service(self, compose):
        assert "dashboard:" in compose

    def test_has_agent_mail_service(self, compose):
        assert "agent-mail:" in compose

    def test_has_outline_service(self, compose):
        assert "outline:" in compose

    def test_has_postgres_service(self, compose):
        assert "postgres:" in compose

    def test_has_redis_service(self, compose):
        assert "redis:" in compose

    def test_has_gorilla_net_network(self, compose):
        assert "gorilla-net:" in compose

    def test_has_named_volumes(self, compose):
        assert "agent-mail-data:" in compose
        assert "postgres-data:" in compose
        assert "redis-data:" in compose

    def test_has_health_checks(self, compose):
        assert "healthcheck:" in compose

    def test_has_restart_policy(self, compose):
        assert "restart: unless-stopped" in compose

    def test_orchestrator_depends_on_agent_mail(self, compose):
        assert "agent-mail:" in compose
        assert "service_healthy" in compose

    def test_dashboard_depends_on_orchestrator(self, compose):
        assert "orchestrator:" in compose


class TestDockerfileOrchestrator:
    @pytest.fixture
    def dockerfile(self) -> str:
        return (INFRA_DIR / "Dockerfile.orchestrator").read_text(encoding="utf-8")

    def test_uses_python_base(self, dockerfile):
        assert "python:3.13" in dockerfile

    def test_installs_requirements(self, dockerfile):
        assert "requirements.txt" in dockerfile

    def test_exposes_port_8000(self, dockerfile):
        assert "8000" in dockerfile

    def test_has_healthcheck(self, dockerfile):
        assert "HEALTHCHECK" in dockerfile

    def test_has_dev_stage(self, dockerfile):
        assert "AS dev" in dockerfile

    def test_copies_orchestrator(self, dockerfile):
        assert "orchestrator/" in dockerfile


class TestDockerfileDashboard:
    @pytest.fixture
    def dockerfile(self) -> str:
        return (INFRA_DIR / "Dockerfile.dashboard").read_text(encoding="utf-8")

    def test_multi_stage_build(self, dockerfile):
        assert "AS build" in dockerfile
        assert "AS prod" in dockerfile

    def test_uses_node_for_build(self, dockerfile):
        assert "node:20-alpine" in dockerfile

    def test_uses_nginx_for_prod(self, dockerfile):
        assert "nginx:alpine" in dockerfile

    def test_copies_build_output(self, dockerfile):
        assert "--from=build" in dockerfile

    def test_copies_nginx_conf(self, dockerfile):
        assert "nginx.conf" in dockerfile

    def test_has_healthcheck(self, dockerfile):
        assert "HEALTHCHECK" in dockerfile


class TestNginxConf:
    @pytest.fixture
    def nginx(self) -> str:
        return (INFRA_DIR / "nginx.conf").read_text(encoding="utf-8")

    def test_listens_on_80(self, nginx):
        assert "listen 80" in nginx

    def test_spa_fallback(self, nginx):
        assert "try_files" in nginx
        assert "index.html" in nginx

    def test_api_proxy(self, nginx):
        assert "proxy_pass http://orchestrator:8000" in nginx

    def test_websocket_proxy(self, nginx):
        assert "Upgrade" in nginx
        assert "upgrade" in nginx
        assert "/ws" in nginx

    def test_gzip_enabled(self, nginx):
        assert "gzip on" in nginx

    def test_cache_headers(self, nginx):
        assert "Cache-Control" in nginx


class TestEnvExample:
    @pytest.fixture
    def env_content(self) -> str:
        return (INFRA_DIR / ".env.example").read_text(encoding="utf-8")

    def test_has_aws_credentials(self, env_content):
        assert "AWS_CONFIG_DIR" in env_content
        assert "AWS_PROFILE" in env_content
        assert "AWS_DEFAULT_REGION" in env_content

    def test_has_port_config(self, env_content):
        assert "ORCHESTRATOR_PORT" in env_content
        assert "DASHBOARD_PORT" in env_content

    def test_has_outline_config(self, env_content):
        assert "OUTLINE_SECRET_KEY" in env_content
        assert "OUTLINE_DB_PASSWORD" in env_content

    def test_has_agent_mail_url(self, env_content):
        assert "AGENT_MAIL_URL" in env_content

    def test_has_project_workspace(self, env_content):
        assert "PROJECT_WORKSPACE" in env_content


class TestProjectReadiness:
    """Verify that the current repo is a valid Harambe project for Docker deployment.

    When the project directory is bind-mounted into the container, the
    orchestrator needs: a .beads/ workspace with its config files, compose
    env vars that point GORILLA_WORKSPACE and DEFAULT_PROJECT_PATH at the
    mount target, no stale beads-data named volume, and .gorilla-troop/
    excluded from git.
    """

    REPO_ROOT = Path(__file__).resolve().parents[2]

    @pytest.fixture
    def compose(self) -> str:
        return (INFRA_DIR / "docker-compose.yml").read_text(encoding="utf-8")

    # ── .beads/ workspace structure ────────────────────────────────

    def test_beads_dir_exists(self):
        assert (self.REPO_ROOT / ".beads").is_dir()

    def test_beads_config_yaml_exists(self):
        assert (self.REPO_ROOT / ".beads" / "config.yaml").is_file()

    def test_beads_metadata_json_exists(self):
        assert (self.REPO_ROOT / ".beads" / "metadata.json").is_file()

    def test_beads_issues_jsonl_exists(self):
        assert (self.REPO_ROOT / ".beads" / "issues.jsonl").is_file()

    # ── Compose wiring ─────────────────────────────────────────────

    def test_no_beads_named_volume(self, compose):
        """beads-data named volume must not exist -- .beads/ comes via bind mount."""
        assert "beads-data" not in compose

    def test_gorilla_workspace_is_configurable(self, compose):
        """GORILLA_WORKSPACE is env-driven so it works for multi-project layouts."""
        assert "GORILLA_WORKSPACE=${GORILLA_WORKSPACE:-/workspace}" in compose

    def test_default_project_path_is_configurable(self, compose):
        """DEFAULT_PROJECT_PATH is env-driven, defaults to aidlc-beads subdir."""
        assert "DEFAULT_PROJECT_PATH=${DEFAULT_PROJECT_PATH:-/workspace/aidlc-beads}" in compose

    def test_workspace_mount_uses_env_var(self, compose):
        """PROJECT_WORKSPACE env var controls the host-side bind mount to /workspace."""
        assert "PROJECT_WORKSPACE" in compose
        assert ":/workspace" in compose

    # ── .gorilla-troop/ excluded from git ──────────────────────────

    def test_gorilla_troop_in_gitignore(self):
        gitignore = (self.REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
        assert ".gorilla-troop/" in gitignore

    # ── Registry round-trip with real project dir ──────────────────

    def test_registry_can_register_project(self, tmp_path):
        """ProjectRegistry can register this repo as a project and read it back."""
        from orchestrator.engine.project_registry import ProjectRegistry

        registry = ProjectRegistry(workspace_root=tmp_path)
        project = registry.create_project(
            key="aidlc-beads",
            name="AIDLC Beads",
            workspace_path=str(self.REPO_ROOT),
        )
        assert project.status == "active"
        assert project.workspace_path == str(self.REPO_ROOT)

        # Reload from disk to prove persistence
        registry2 = ProjectRegistry(workspace_root=tmp_path)
        reloaded = registry2.get_project("aidlc-beads")
        assert reloaded is not None
        assert reloaded.name == "AIDLC Beads"

    def test_find_workspace_root_succeeds(self):
        """find_workspace_root() locates .beads/ from the repo root."""
        from orchestrator.lib.scribe.workspace import find_workspace_root

        root = find_workspace_root(start=self.REPO_ROOT)
        assert root == self.REPO_ROOT


class TestRequirementsTxt:
    def test_exists(self):
        req_path = Path(__file__).resolve().parents[2] / "requirements.txt"
        assert req_path.exists()

    def test_has_core_deps(self):
        req_path = Path(__file__).resolve().parents[2] / "requirements.txt"
        content = req_path.read_text(encoding="utf-8")
        assert "fastapi" in content
        assert "uvicorn" in content
        assert "httpx" in content
        assert "pydantic" in content
        assert "click" in content
