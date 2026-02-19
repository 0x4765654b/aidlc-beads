"""File upload/download routes for project workspaces."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from orchestrator.api.deps import get_registry, get_ws_manager
from orchestrator.api.models import WriteFileRequest, FileResponse, FileContentResponse
from orchestrator.engine.project_registry import ProjectRegistry
from orchestrator.api.websocket import ConnectionManager

logger = logging.getLogger("api.files")

router = APIRouter(prefix="/api/projects", tags=["files"])


@router.post("/{project_key}/files", response_model=FileResponse, status_code=201)
async def write_file(
    project_key: str,
    body: WriteFileRequest,
    registry: ProjectRegistry = Depends(get_registry),
    ws: ConnectionManager = Depends(get_ws_manager),
) -> FileResponse:
    """Write a file to the project workspace."""
    project = registry.get_project(project_key)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_key}' not found")

    # Reject path traversal
    if ".." in body.path:
        raise HTTPException(status_code=400, detail="Path traversal ('..') not allowed")

    # Reject absolute paths
    if body.path.startswith("/") or body.path.startswith("\\"):
        raise HTTPException(status_code=400, detail="Absolute paths not allowed")

    workspace = Path(project.workspace_path)
    dest = (workspace / body.path).resolve()

    # Ensure resolved path is still inside workspace
    try:
        dest.relative_to(workspace.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Path resolves outside workspace")

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(body.content, encoding="utf-8")

    now = datetime.now(timezone.utc).isoformat()
    logger.info("[FILES] Wrote %s (%d bytes) to %s", body.path, len(body.content), project_key)

    await ws.broadcast(
        "file_uploaded",
        project_key,
        {"project_key": project_key, "path": body.path, "size_bytes": len(body.content)},
    )

    return FileResponse(
        project_key=project_key,
        path=body.path,
        size_bytes=len(body.content),
        written_at=now,
    )


@router.get("/{project_key}/files", response_model=FileContentResponse)
async def read_file(
    project_key: str,
    path: str,
    registry: ProjectRegistry = Depends(get_registry),
) -> FileContentResponse:
    """Read a file from the project workspace."""
    project = registry.get_project(project_key)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_key}' not found")

    # Reject path traversal
    if ".." in path:
        raise HTTPException(status_code=400, detail="Path traversal ('..') not allowed")

    if path.startswith("/") or path.startswith("\\"):
        raise HTTPException(status_code=400, detail="Absolute paths not allowed")

    workspace = Path(project.workspace_path)
    target = (workspace / path).resolve()

    try:
        target.relative_to(workspace.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Path resolves outside workspace")

    if not target.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")

    content = target.read_text(encoding="utf-8")
    return FileContentResponse(
        path=path,
        content=content,
        size_bytes=len(content),
    )
