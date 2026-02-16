"""Project management routes -- CRUD, status, agent listing."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from orchestrator.api.deps import get_registry, get_engine, get_ws_manager
from orchestrator.api.models import (
    CreateProjectRequest,
    ProjectResponse,
    ProjectStatusResponse,
    AgentResponse,
)
from orchestrator.engine.project_registry import ProjectRegistry, ProjectState
from orchestrator.engine.agent_engine import AgentEngine
from orchestrator.api.websocket import ConnectionManager

logger = logging.getLogger("api.projects")

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _project_to_response(project: ProjectState) -> ProjectResponse:
    """Convert internal ProjectState to API response."""
    return ProjectResponse(
        project_key=project.project_key,
        name=project.name,
        workspace_path=project.workspace_path,
        status=project.status,
        minder_agent_id=project.minder_agent_id,
        created_at=project.created_at,
        paused_at=project.paused_at,
    )


@router.post("/", response_model=ProjectResponse, status_code=201)
async def create_project(
    body: CreateProjectRequest,
    registry: ProjectRegistry = Depends(get_registry),
    ws: ConnectionManager = Depends(get_ws_manager),
) -> ProjectResponse:
    """Create a new project."""
    # Validate workspace path exists
    workspace = Path(body.workspace_path)
    if not workspace.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Workspace path does not exist or is not a directory: {body.workspace_path}",
        )

    # Reject path traversal
    try:
        workspace.resolve(strict=True)
    except (OSError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid workspace path")

    if ".." in str(body.workspace_path):
        raise HTTPException(status_code=400, detail="Path traversal not allowed")

    try:
        project = registry.create_project(body.key, body.name, body.workspace_path)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    await ws.broadcast(
        "project_created", body.key, {"project_key": body.key, "name": body.name}
    )

    logger.info("Created project: %s", body.key)
    return _project_to_response(project)


@router.get("/", response_model=list[ProjectResponse])
async def list_projects(
    status: str | None = None,
    registry: ProjectRegistry = Depends(get_registry),
) -> list[ProjectResponse]:
    """List all projects, optionally filtered by status."""
    projects = registry.list_projects(status=status)
    return [_project_to_response(p) for p in projects]


@router.get("/{project_key}", response_model=ProjectResponse)
async def get_project(
    project_key: str,
    registry: ProjectRegistry = Depends(get_registry),
) -> ProjectResponse:
    """Get a single project by key."""
    project = registry.get_project(project_key)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_key}' not found")
    return _project_to_response(project)


@router.post("/{project_key}/pause", response_model=ProjectResponse)
async def pause_project(
    project_key: str,
    registry: ProjectRegistry = Depends(get_registry),
    ws: ConnectionManager = Depends(get_ws_manager),
) -> ProjectResponse:
    """Pause a project."""
    try:
        registry.pause_project(project_key)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Project '{project_key}' not found")

    project = registry.get_project(project_key)
    await ws.broadcast("project_paused", project_key, {"project_key": project_key})
    return _project_to_response(project)  # type: ignore[arg-type]


@router.post("/{project_key}/resume", response_model=ProjectResponse)
async def resume_project(
    project_key: str,
    registry: ProjectRegistry = Depends(get_registry),
    ws: ConnectionManager = Depends(get_ws_manager),
) -> ProjectResponse:
    """Resume a paused project."""
    try:
        registry.resume_project(project_key)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Project '{project_key}' not found")

    project = registry.get_project(project_key)
    await ws.broadcast("project_resumed", project_key, {"project_key": project_key})
    return _project_to_response(project)  # type: ignore[arg-type]


@router.delete("/{project_key}", status_code=204)
async def delete_project(
    project_key: str,
    registry: ProjectRegistry = Depends(get_registry),
    ws: ConnectionManager = Depends(get_ws_manager),
) -> None:
    """Delete a project."""
    try:
        registry.delete_project(project_key)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Project '{project_key}' not found")

    await ws.broadcast("project_deleted", project_key, {"project_key": project_key})
    logger.info("Deleted project: %s", project_key)


@router.get("/{project_key}/status", response_model=ProjectStatusResponse)
async def get_project_status(
    project_key: str,
    registry: ProjectRegistry = Depends(get_registry),
    engine: AgentEngine = Depends(get_engine),
) -> ProjectStatusResponse:
    """Get detailed project status with agent and workflow info."""
    project = registry.get_project(project_key)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_key}' not found")

    active_agents = [a for a in engine.list_active() if a.project_key == project_key]

    return ProjectStatusResponse(
        project_key=project.project_key,
        name=project.name,
        status=project.status,
        active_agents=len(active_agents),
    )


@router.get("/{project_key}/agents", response_model=list[AgentResponse])
async def list_project_agents(
    project_key: str,
    registry: ProjectRegistry = Depends(get_registry),
    engine: AgentEngine = Depends(get_engine),
) -> list[AgentResponse]:
    """List active agents for a project."""
    project = registry.get_project(project_key)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_key}' not found")

    agents = [a for a in engine.list_active() if a.project_key == project_key]
    return [
        AgentResponse(
            agent_id=a.agent_id,
            agent_type=a.agent_type,
            status=a.status,
            current_task=a.current_task,
            created_at=a.created_at.isoformat(),
        )
        for a in agents
    ]
