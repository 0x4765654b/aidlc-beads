"""Cross-cutting agents -- Bonobo, Groomer, Snake, CuriousGeorge, Gibbon."""

from orchestrator.agents.cross_cutting.bonobo_agent import BonoboAgent
from orchestrator.agents.cross_cutting.groomer import Groomer
from orchestrator.agents.cross_cutting.snake import Snake
from orchestrator.agents.cross_cutting.curious_george import CuriousGeorge
from orchestrator.agents.cross_cutting.gibbon import Gibbon

__all__ = ["BonoboAgent", "Groomer", "Snake", "CuriousGeorge", "Gibbon"]
