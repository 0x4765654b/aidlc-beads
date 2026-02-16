"""Bonobo Write Guards -- privileged operation gatekeeper for Gorilla Troop.

Every write operation (filesystem, Git, Beads) is validated and audited
through a guard before execution. No agent writes directly.
"""

from orchestrator.lib.bonobo.audit import AuditLog, AuditEntry
from orchestrator.lib.bonobo.file_guard import FileGuard
from orchestrator.lib.bonobo.git_guard import GitGuard
from orchestrator.lib.bonobo.beads_guard import BeadsGuard

__all__ = [
    "AuditLog",
    "AuditEntry",
    "FileGuard",
    "GitGuard",
    "BeadsGuard",
]
