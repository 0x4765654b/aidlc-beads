"""Operator experience — formatted console output for Rafiki runs."""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from rafiki.models import (
    ReviewDecisionRecord,
    QuestionAnswerRecord,
    ChatRecord,
    VerificationResult,
    RunReport,
)

logger = logging.getLogger("rafiki.display")

SEPARATOR = "=" * 63
THIN_SEP = "-" * 63


class Display:
    """Formats and prints operator-facing console output."""

    def __init__(self, log_format: str = "text", file: Any = None):
        self._fmt = log_format  # "text" or "json"
        self._file = file or sys.stdout

    def _now(self) -> str:
        return datetime.now(timezone.utc).strftime("%H:%M:%S")

    def _print(self, text: str) -> None:
        try:
            print(text, file=self._file, flush=True)
        except UnicodeEncodeError:
            # Windows cp1252 can't handle some Unicode chars (emojis, etc.)
            safe = text.encode(self._file.encoding or "utf-8", errors="replace").decode(
                self._file.encoding or "utf-8", errors="replace"
            )
            print(safe, file=self._file, flush=True)

    def _json_line(self, **kwargs: Any) -> None:
        kwargs.setdefault("ts", datetime.now(timezone.utc).isoformat())
        print(json.dumps(kwargs, default=str), file=self._file, flush=True)

    # ── Startup Banner ────────────────────────────────────────────────

    def banner(
        self,
        *,
        version: str = "",
        run_id: str = "",
        api_url: str = "",
        api_healthy: bool = False,
        ws_url: str = "",
        ws_connected: bool = False,
        project_key: str = "",
        project_name: str = "",
        mode: str = "",
    ) -> None:
        if self._fmt == "json":
            self._json_line(
                event="run_started", version=version, run_id=run_id,
                api_url=api_url, api_healthy=api_healthy,
                ws_url=ws_url, ws_connected=ws_connected,
                project_key=project_key, mode=mode,
            )
            return

        api_mark = "[OK] healthy" if api_healthy else "[FAIL] UNREACHABLE"
        ws_mark = "[OK] connected" if ws_connected else "[FAIL] disconnected"
        self._print(f"\n{SEPARATOR}")
        self._print(f"  Rafiki — Human Simulation Agent  v{version}")
        self._print(f"  Run ID:    {run_id}")
        self._print(f"  API:       {api_url} {api_mark}")
        self._print(f"  WebSocket: {ws_url} {ws_mark}")
        self._print(f"  Project:   {project_key} ({project_name})")
        self._print(f"  Mode:      {mode}")
        self._print(f"{SEPARATOR}\n")

    # ── Rolling Log ───────────────────────────────────────────────────

    def log(self, state: str, message: str, details: list[str] | None = None) -> None:
        if self._fmt == "json":
            self._json_line(event="log", state=state, detail=message)
            return

        self._print(f"[{self._now()}] {state:<20s} {message}")
        if details:
            for i, d in enumerate(details):
                prefix = "|--" if i < len(details) - 1 else "`--"
                self._print(f"{'':>29s}{prefix} {d}")

    # ── Review Handling ───────────────────────────────────────────────

    def review(self, record: ReviewDecisionRecord) -> None:
        if self._fmt == "json":
            self._json_line(
                event="review_decision", state="HANDLING_REVIEW",
                issue_id=record.issue_id, decision=record.decision,
                strategy=record.strategy, detail=record.feedback[:200],
            )
            return

        self._print(f"[{self._now()}] {'HANDLING_REVIEW':<20s} Review gate: {record.issue_id}")
        self._print(f"{'':>29s}|-- Strategy: {record.strategy}")
        feedback_preview = record.feedback[:120].replace("\n", " ")
        self._print(f"{'':>29s}|-- Feedback: {feedback_preview}")
        self._print(f"{'':>29s}`-- Decision: {record.decision.upper()}")

    # ── Question Handling ─────────────────────────────────────────────

    def question(self, record: QuestionAnswerRecord) -> None:
        if self._fmt == "json":
            self._json_line(
                event="question_answered", state="HANDLING_QUESTION",
                issue_id=record.issue_id, answer=record.answer,
                strategy=record.strategy, detail=record.rationale[:200],
            )
            return

        self._print(f"[{self._now()}] {'HANDLING_QUESTION':<20s} Q: {record.issue_id}")
        self._print(f"{'':>29s}|-- Strategy: {record.strategy}")
        self._print(f"{'':>29s}`-- Answer: {record.answer}")

    # ── Chat Interactions ─────────────────────────────────────────────

    def chat(self, prompt: str, response: str) -> None:
        if self._fmt == "json":
            self._json_line(
                event="chat_interaction", state="CHATTING",
                detail=prompt, response=response[:200],
            )
            return

        self._print(f"[{self._now()}] {'CHATTING':<20s} Chat: \"{prompt}\"")
        response_preview = response[:120].replace("\n", " ")
        self._print(f"{'':>29s}`-- Harmbe: \"{response_preview}\"")

    # ── Stall Alerts ──────────────────────────────────────────────────

    def stall(
        self,
        stall_minutes: float,
        issue_id: str,
        chat_prompt: str,
        chat_response: str,
        stall_count: int,
        max_stalls: int,
    ) -> None:
        if self._fmt == "json":
            self._json_line(
                event="stall_detected", state="STALLED",
                stall_minutes=stall_minutes, issue_id=issue_id,
                stall_count=stall_count, max_stalls=max_stalls,
            )
            return

        self._print(f"[{self._now()}] {'STALLED':<20s} No progress for {stall_minutes:.0f}m")
        if issue_id:
            self._print(f"{'':>29s}|-- Filed: {issue_id}")
        self._print(f"{'':>29s}|-- Chat: \"{chat_prompt}\"")
        response_preview = chat_response[:120].replace("\n", " ")
        self._print(f"{'':>29s}`-- Harmbe: \"{response_preview}\"")
        self._print(f"[{self._now()}] {'MONITORING':<20s} Resuming monitoring (stall {stall_count}/{max_stalls})...")

    # ── Verification Checklist ────────────────────────────────────────

    def verification_check(self, result: VerificationResult) -> None:
        if self._fmt == "json":
            self._json_line(
                event="verification_check", state="VERIFYING",
                name=result.name, passed=result.passed,
                detail=result.detail, duration_ms=result.duration_ms,
            )
            return

        mark = "PASS" if result.passed else "FAIL"
        self._print(f"[{self._now()}] {'VERIFYING':<20s} {result.name:<30s} {mark} {result.detail}")

    # ── Cleanup Progress ──────────────────────────────────────────────

    def cleanup_step(self, step: str) -> None:
        if self._fmt == "json":
            self._json_line(event="cleanup_step", state="CLEANING_UP", detail=step)
            return

        self._print(f"[{self._now()}] {'CLEANING_UP':<20s} {step}")

    # ── Final Summary Banner ──────────────────────────────────────────

    def summary_banner(self, report: RunReport | None) -> None:
        if report is None:
            self._print(f"\n{SEPARATOR}\n  Rafiki Run Complete (no report generated)\n{SEPARATOR}\n")
            return

        if self._fmt == "json":
            self._json_line(
                event="run_complete", outcome=report.outcome,
                duration_seconds=report.duration_seconds,
                reviews=len(report.reviews_handled),
                questions=len(report.questions_answered),
                chats=len(report.chat_interactions),
                stalls=report.stalls_detected,
                issues_filed=report.issues_filed_count,
                verification=report.verification.overall,
            )
            return

        duration_str = _format_duration(report.duration_seconds)
        v = report.verification
        passed_count = sum(1 for c in v.checks if c.passed)
        total_count = len(v.checks)

        self._print(f"\n{SEPARATOR}")
        self._print(f"  Rafiki Run Complete")
        self._print(f"{THIN_SEP}")
        outcome_str = report.outcome
        if report.issues_filed_count > 0:
            outcome_str += f" (with {report.issues_filed_count} issues filed)"
        self._print(f"  Outcome:      {outcome_str}")
        self._print(f"  Duration:     {duration_str}")
        self._print(f"  Reviews:      {len(report.reviews_handled)} handled")
        self._print(f"  Questions:    {len(report.questions_answered)} answered")
        self._print(f"  Chats:        {len(report.chat_interactions)} interactions")
        self._print(f"  Stalls:       {report.stalls_detected}")
        self._print(f"  Issues filed: {report.issues_filed_count}")
        self._print(f"  Verification: {passed_count}/{total_count} passed")
        self._print(f"{THIN_SEP}")
        self._print(f"  Report: {report.run_id}-report.json")

        if report.issues_filed:
            self._print(f"  Beads issues to fix:")
            for issue in report.issues_filed:
                self._print(f"    {issue.issue_id}  P{issue.priority} {issue.type}  {issue.title}")

        self._print(f"{SEPARATOR}\n")


def _format_duration(seconds: float) -> str:
    """Format seconds as Xh Ym Zs."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}h {m:02d}m {s:02d}s"
    return f"{m}m {s:02d}s"
