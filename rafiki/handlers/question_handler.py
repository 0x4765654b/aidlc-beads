"""Q&A question handler — context-aware option selection."""
from __future__ import annotations

import logging
import re
from rafiki.models import QuestionAnswerRecord

logger = logging.getLogger("rafiki.handlers.question")

# Pattern to match A) Option text, B) Option text, etc.
OPTION_PATTERN = re.compile(r"^([A-Z])\)\s*(.+)$", re.MULTILINE)


class QuestionHandler:
    """Answers Q&A questions using context matching and optional LLM."""

    def __init__(
        self,
        question_client,  # QuestionClient
        issue_filer,      # IssueFiler
        *,
        llm_enabled: bool = True,
        vision_text: str = "",
        tech_env_text: str = "",
    ):
        self.question_client = question_client
        self.issue_filer = issue_filer
        self.llm_enabled = llm_enabled
        self.vision_text = vision_text
        self.tech_env_text = tech_env_text

    async def handle(self, question: dict) -> QuestionAnswerRecord:
        """Answer a Q&A question."""
        issue_id = question.get("issue_id", "")
        title = question.get("title", "")
        description = question.get("description", "")

        # Step 1 — Parse options
        options = self._parse_options(description)
        if not options:
            # No structured options; answer with a generic response
            logger.warning("No structured options found in question %s", issue_id)
            await self.question_client.answer(issue_id, "Acknowledged — no structured options detected.")
            await self.issue_filer.file_task(
                f"Rafiki: Could not parse options for question {issue_id}",
                f"Question '{title}' had no parseable A/B/C options.\n\nDescription:\n{description[:500]}",
                priority=2,
                source="qa",
            )
            return QuestionAnswerRecord(
                issue_id=issue_id, answer="Acknowledged",
                rationale="No structured options found", strategy="fallback",
            )

        # Step 2 — Context matching
        scored = self._score_options(options, title, description)
        best_non_other = [(letter, text, score) for letter, text, score in scored if letter != "X"]
        best_other = [(letter, text, score) for letter, text, score in scored if letter == "X"]

        if best_non_other:
            top = max(best_non_other, key=lambda x: x[2])
            runner_up_scores = sorted([s for _, _, s in best_non_other], reverse=True)
            scores_are_close = len(runner_up_scores) > 1 and (runner_up_scores[0] - runner_up_scores[1]) < 2
        else:
            top = best_other[0] if best_other else (scored[0] if scored else ("A", "Unknown", 0))
            scores_are_close = False

        # Step 3 — LLM tiebreaker if scores are close
        if scores_are_close and self.llm_enabled:
            llm_pick = await self._llm_select(title, description, options)
            if llm_pick:
                selected_letter = llm_pick["letter"]
                rationale = llm_pick.get("rationale", "LLM tiebreaker")
                strategy = "llm"
            else:
                selected_letter = top[0]
                rationale = f"Context match (score {top[2]}); LLM unavailable"
                strategy = "context_match"
        else:
            selected_letter = top[0]
            rationale = f"Context match (score {top[2]})"
            strategy = "context_match"

        # Step 4 — Submit answer
        selected_text = next((t for l, t in options if l == selected_letter), selected_letter)
        answer_text = f"{selected_letter}) {selected_text}"
        logger.info("Answering question %s: %s", issue_id, answer_text)
        await self.question_client.answer(issue_id, answer_text)

        # If scores were ambiguous, file a task
        if scores_are_close and strategy != "llm":
            await self.issue_filer.file_task(
                f"Rafiki: Ambiguous question answer for {issue_id}",
                f"Question '{title}' had close context scores; defaulted to {answer_text}.",
                priority=2,
                source="qa",
            )

        return QuestionAnswerRecord(
            issue_id=issue_id, answer=answer_text,
            rationale=rationale, strategy=strategy,
        )

    @staticmethod
    def _parse_options(description: str) -> list[tuple[str, str]]:
        """Parse A) Option, B) Option, X) Other from description text."""
        matches = OPTION_PATTERN.findall(description)
        return [(letter, text.strip()) for letter, text in matches]

    def _score_options(
        self, options: list[tuple[str, str]], title: str, description: str,
    ) -> list[tuple[str, str, int]]:
        """Score each option against project context. Returns (letter, text, score)."""
        context = f"{self.vision_text}\n{self.tech_env_text}".lower()
        scored = []
        for letter, text in options:
            score = 0
            text_lower = text.lower()
            words = re.findall(r"\w+", text_lower)
            for word in words:
                if len(word) > 3 and word in context:
                    score += 1
            # Penalize "Other" heavily
            if letter == "X" or "other" in text_lower:
                score -= 10
            # Boost options matching known tech stack keywords
            tech_keywords = ["python", "fastapi", "pytest", "ruff", "uv", "pydantic", "httpx", "asyncio"]
            for kw in tech_keywords:
                if kw in text_lower:
                    score += 3
            scored.append((letter, text, score))
        return scored

    async def _llm_select(self, title: str, description: str, options: list[tuple[str, str]]) -> dict | None:
        """Use LLM to select the best option. Returns dict with 'letter' and 'rationale' or None."""
        # Stub — in production this calls Bedrock
        logger.info("LLM tiebreaker for question (stub: returning None)")
        return None
