"""Context Dispatch Protocol for Gorilla Troop."""

from orchestrator.lib.context.dispatch import (
    DispatchMessage,
    CompletionMessage,
    build_dispatch,
    build_completion,
    serialize_dispatch,
    deserialize_dispatch,
    serialize_completion,
    deserialize_completion,
    STAGE_AGENT_MAP,
)

__all__ = [
    "DispatchMessage",
    "CompletionMessage",
    "build_dispatch",
    "build_completion",
    "serialize_dispatch",
    "deserialize_dispatch",
    "serialize_completion",
    "deserialize_completion",
    "STAGE_AGENT_MAP",
]
