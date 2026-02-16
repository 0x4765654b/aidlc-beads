"""Chimp agents -- 8 specialist workers for AIDLC stages."""

from orchestrator.agents.chimps.base_chimp import BaseChimp
from orchestrator.agents.chimps.scout import Scout
from orchestrator.agents.chimps.sage import Sage
from orchestrator.agents.chimps.bard import Bard
from orchestrator.agents.chimps.planner import Planner
from orchestrator.agents.chimps.architect import Architect
from orchestrator.agents.chimps.steward import Steward
from orchestrator.agents.chimps.forge import Forge
from orchestrator.agents.chimps.crucible import Crucible

__all__ = [
    "BaseChimp",
    "Scout", "Sage", "Bard", "Planner",
    "Architect", "Steward", "Forge", "Crucible",
]
