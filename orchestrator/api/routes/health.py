"""Health and system info routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from orchestrator.api.deps import get_registry, get_engine, get_notifications
from orchestrator.api.models import SystemInfoResponse
from orchestrator.engine.project_registry import ProjectRegistry
from orchestrator.engine.agent_engine import AgentEngine
from orchestrator.engine.notification_manager import NotificationManager

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    """Liveness check -- always returns ok if the server is running."""
    return {"status": "ok"}


@router.get("/info", response_model=SystemInfoResponse)
async def system_info(
    registry: ProjectRegistry = Depends(get_registry),
    engine: AgentEngine = Depends(get_engine),
    notifications: NotificationManager = Depends(get_notifications),
) -> SystemInfoResponse:
    """System information snapshot."""
    active_projects = len(registry.list_projects(status="active"))
    active_agents = len(engine.list_active())
    pending = notifications.count_unread()
    engine_status = "shutting_down" if engine._shutdown_event.is_set() else "running"

    return SystemInfoResponse(
        version="0.1.0",
        active_projects=active_projects,
        active_agents=active_agents,
        pending_notifications=pending,
        engine_status=engine_status,
    )
