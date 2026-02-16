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
        assert "beads-data:" in compose
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
        assert "AWS_ACCESS_KEY_ID" in env_content
        assert "AWS_SECRET_ACCESS_KEY" in env_content
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
