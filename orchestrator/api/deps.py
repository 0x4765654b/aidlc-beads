"""FastAPI dependency injection functions for shared state."""

from __future__ import annotations

import logging
from functools import lru_cache

from fastapi import Request

from orchestrator.engine.project_registry import ProjectRegistry
from orchestrator.engine.agent_engine import AgentEngine
from orchestrator.engine.notification_manager import NotificationManager
from orchestrator.engine.log_buffer import LogBuffer

logger = logging.getLogger("api.deps")

# Lazy-initialized singletons for Beads and Agent Mail clients
_beads_client_module = None
_agent_mail_client = None


def get_registry(request: Request) -> ProjectRegistry:
    """Get the shared ProjectRegistry from app state."""
    return request.app.state.registry


def get_engine(request: Request) -> AgentEngine:
    """Get the shared AgentEngine from app state."""
    return request.app.state.engine


def get_notifications(request: Request) -> NotificationManager:
    """Get the shared NotificationManager from app state."""
    return request.app.state.notifications


def get_ws_manager(request: Request):
    """Get the shared ConnectionManager from app state."""
    return request.app.state.ws_manager


def get_log_buffer(request: Request) -> LogBuffer:
    """Get the shared LogBuffer from app state."""
    return request.app.state.log_buffer


def get_beads_client():
    """Get the Beads CLI client module.

    Returns the orchestrator.lib.beads.client module which provides
    functions like list_issues(), show_issue(), update_issue(), etc.
    Returns None if the module cannot be imported.
    """
    global _beads_client_module
    if _beads_client_module is None:
        try:
            from orchestrator.lib.beads import client as bc
            _beads_client_module = bc
        except Exception as e:
            logger.warning("Could not import beads client: %s", e)
            return None
    return _beads_client_module


def get_mail_client():
    """Get the shared Agent Mail client.

    Returns an AgentMailClient instance or None if unavailable.
    """
    global _agent_mail_client
    if _agent_mail_client is None:
        try:
            from orchestrator.lib.agent_mail.client import AgentMailClient
            _agent_mail_client = AgentMailClient()
            logger.info("Agent Mail client initialized")
        except Exception as e:
            logger.warning("Could not create Agent Mail client: %s", e)
            return None
    return _agent_mail_client
