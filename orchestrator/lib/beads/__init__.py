"""Beads CLI client library for Gorilla Troop agents."""

from orchestrator.lib.beads.client import (
    create_issue,
    show_issue,
    update_issue,
    close_issue,
    reopen_issue,
    list_issues,
    ready,
    blocked,
    add_dependency,
    remove_dependency,
    sync,
    search,
)
from orchestrator.lib.beads.models import BeadsIssue, BeadsDependency

__all__ = [
    "create_issue",
    "show_issue",
    "update_issue",
    "close_issue",
    "reopen_issue",
    "list_issues",
    "ready",
    "blocked",
    "add_dependency",
    "remove_dependency",
    "sync",
    "search",
    "BeadsIssue",
    "BeadsDependency",
]
