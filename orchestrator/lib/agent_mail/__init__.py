"""Agent Mail HTTP client library for Gorilla Troop agents."""

from orchestrator.lib.agent_mail.client import AgentMailClient
from orchestrator.lib.agent_mail.models import (
    AgentMailConfig,
    MailMessage,
    FileReservation,
    AgentInfo,
)

__all__ = [
    "AgentMailClient",
    "AgentMailConfig",
    "MailMessage",
    "FileReservation",
    "AgentInfo",
]
