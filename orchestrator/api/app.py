"""FastAPI application factory for the Gorilla Troop Orchestrator API."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

# Configure root logger so all application logs are visible in container output
logging.basicConfig(
    level=os.environ.get("GORILLA_LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
from fastapi.middleware.cors import CORSMiddleware

from orchestrator.config import get_config
from orchestrator.engine.project_registry import ProjectRegistry
from orchestrator.engine.agent_engine import AgentEngine
from orchestrator.engine.notification_manager import NotificationManager
from orchestrator.engine.log_buffer import LogBuffer, BufferHandler
from orchestrator.api.websocket import ConnectionManager

logger = logging.getLogger("api")

VERSION = "0.1.0"


def create_app(
    project_registry: ProjectRegistry | None = None,
    agent_engine: AgentEngine | None = None,
    notification_manager: NotificationManager | None = None,
    log_buffer: LogBuffer | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    All dependencies are injectable for testing. When called with no
    arguments, sensible defaults are created.

    Args:
        project_registry: Injected project registry (creates default if None).
        agent_engine: Injected agent engine (creates default if None).
        notification_manager: Injected notification manager (creates default if None).
        log_buffer: Injected log buffer (creates default if None).

    Returns:
        Configured FastAPI instance.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Application lifespan -- wire engine on start, shutdown on exit."""
        logger.info("Gorilla Troop Orchestrator API v%s starting", VERSION)

        # Wire Strands agents into the engine at startup
        try:
            from orchestrator.wiring import wire_engine

            wire_engine(app.state.engine)
            logger.info("[STARTUP] Agent engine wired — runners: %s", list(app.state.engine._runners.keys()))
        except Exception as e:
            logger.error(
                "[STARTUP] FAILED to wire agents (engine has NO runners): %s", e, exc_info=True
            )

        # Auto-register default project if configured
        try:
            cfg = get_config()
            if cfg.default_project_key and cfg.default_project_path:
                registry = app.state.registry
                if registry.get_project(cfg.default_project_key) is None:
                    workspace = Path(cfg.default_project_path)
                    if workspace.is_dir():
                        registry.create_project(
                            key=cfg.default_project_key,
                            name=cfg.default_project_name or cfg.default_project_key,
                            workspace_path=cfg.default_project_path,
                        )
                        logger.info(
                            "Auto-registered default project: %s at %s",
                            cfg.default_project_key,
                            cfg.default_project_path,
                        )
                    else:
                        logger.warning(
                            "Default project workspace does not exist, skipping auto-register: %s",
                            cfg.default_project_path,
                        )
                else:
                    logger.info(
                        "Default project '%s' already registered, skipping",
                        cfg.default_project_key,
                    )
        except Exception as e:
            logger.warning("Failed to auto-register default project: %s", e)

        yield
        logger.info("Shutting down Orchestrator API")
        if hasattr(app.state, "engine"):
            await app.state.engine.shutdown()

    app = FastAPI(
        title="Gorilla Troop Orchestrator API",
        description="REST + WebSocket backend for the Harmbe Dashboard.",
        version=VERSION,
        lifespan=lifespan,
    )

    # ── Shared state ──────────────────────────────────────────────────
    app.state.registry = project_registry or ProjectRegistry(
        workspace_root=Path(get_config().workspace_root)
    )
    app.state.engine = agent_engine or AgentEngine()
    app.state.notifications = notification_manager or NotificationManager()
    app.state.ws_manager = ConnectionManager()
    app.state.log_buffer = log_buffer or LogBuffer()

    # Attach a BufferHandler to the root logger so all log records are
    # captured in the ring buffer (zero changes to existing logging code).
    _buffer_handler = BufferHandler(app.state.log_buffer)
    _buffer_handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
    logging.getLogger().addHandler(_buffer_handler)

    # ── CORS ──────────────────────────────────────────────────────────
    allowed_origins = os.environ.get(
        "ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:9741"
    ).split(",")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ───────────────────────────────────────────────────────
    from orchestrator.api.routes.health import router as health_router
    from orchestrator.api.routes.projects import router as projects_router
    from orchestrator.api.routes.chat import router as chat_router
    from orchestrator.api.routes.review import router as review_router
    from orchestrator.api.routes.notifications import router as notifications_router
    from orchestrator.api.routes.questions import router as questions_router
    from orchestrator.api.routes.logs import router as logs_router
    from orchestrator.api.routes.files import router as files_router
    from orchestrator.api.routes.ws import router as ws_router

    app.include_router(health_router)
    app.include_router(projects_router)
    app.include_router(chat_router)
    app.include_router(review_router)
    app.include_router(notifications_router)
    app.include_router(questions_router)
    app.include_router(logs_router)
    app.include_router(files_router)
    app.include_router(ws_router)

    return app
