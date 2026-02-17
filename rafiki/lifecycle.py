"""Lifecycle controller — the main Rafiki orchestration loop."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from rafiki import __version__
from rafiki.config import RafikiConfig
from rafiki.models import (
    LifecycleState,
    StateTransition,
    RafikiState,
    RunReport,
    VerificationReport,
)
from rafiki.client import (
    HealthClient,
    ProjectClient,
    ReviewClient,
    QuestionClient,
    ChatClient,
    NotificationClient,
    LogsClient,
    WebSocketListener,
)
from rafiki.handlers import ReviewHandler, QuestionHandler, ChatHandler
from rafiki.monitor import Monitor
from rafiki.issues import IssueFiler
from rafiki.cleanup import run_cleanup
from rafiki.verifier import Verifier
from rafiki.report import generate_report

logger = logging.getLogger("rafiki.lifecycle")

try:
    from rafiki.display import Display
except ImportError:

    class Display:
        """Null display — no-ops for all methods."""

        def __getattr__(self, _):
            return lambda *a, **kw: None


class LifecycleController:
    """Drives a Rafiki run through the complete lifecycle state machine."""

    def __init__(self, config: RafikiConfig, workspace_root: Path):
        self.config = config
        self.workspace_root = workspace_root
        self.run_id = f"rafiki-{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H-%M-%S')}"

        # State
        self.state = RafikiState(
            run_id=self.run_id,
            project_key=config.project_key,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        self._current_state = LifecycleState.INITIALIZING
        self._start_time = time.monotonic()

        # Clients (initialized in _init_clients)
        self._health_client: HealthClient | None = None
        self._project_client: ProjectClient | None = None
        self._review_client: ReviewClient | None = None
        self._question_client: QuestionClient | None = None
        self._chat_client: ChatClient | None = None
        self._notification_client: NotificationClient | None = None
        self._logs_client: LogsClient | None = None
        self._ws_listener: WebSocketListener | None = None

        # Components
        self._monitor: Monitor | None = None
        self._review_handler: ReviewHandler | None = None
        self._question_handler: QuestionHandler | None = None
        self._chat_handler: ChatHandler | None = None
        self._issue_filer = IssueFiler(workspace_root, self.run_id)
        self._verifier: Verifier | None = None
        self._display = Display()

        # Project context (loaded from rafiki-project/)
        self._vision_text = ""
        self._tech_env_text = ""

    def _set_state(self, new_state: LifecycleState) -> None:
        """Transition to a new lifecycle state."""
        now = datetime.now(timezone.utc).isoformat()
        self.state.state_transitions.append(
            StateTransition(state=new_state.value, entered_at=now)
        )
        self.state.current_state = new_state.value
        self._current_state = new_state
        logger.info("State -> %s", new_state.value)

    def _elapsed_seconds(self) -> float:
        return time.monotonic() - self._start_time

    def _load_project_context(self) -> None:
        """Load vision.md and tech-env.md from the project workspace."""
        project_dir = self.config.resolve_workspace(self.workspace_root)
        vision_path = project_dir / "vision.md"
        tech_path = project_dir / "tech-env.md"
        if vision_path.exists():
            self._vision_text = vision_path.read_text(encoding="utf-8")
        if tech_path.exists():
            self._tech_env_text = tech_path.read_text(encoding="utf-8")

    def _init_clients(self) -> None:
        """Create all API client instances."""
        url = self.config.api_url
        self._health_client = HealthClient(url)
        self._project_client = ProjectClient(url)
        self._review_client = ReviewClient(url)
        self._question_client = QuestionClient(url)
        self._chat_client = ChatClient(url)
        self._notification_client = NotificationClient(url)
        self._logs_client = LogsClient(url)
        self._ws_listener = WebSocketListener()

    def _init_handlers(self) -> None:
        """Create handler instances."""
        self._review_handler = ReviewHandler(
            self._review_client,
            self._issue_filer,
            auto_approve=self.config.auto_approve,
            llm_enabled=self.config.llm_enabled,
            vision_text=self._vision_text,
            tech_env_text=self._tech_env_text,
        )
        self._question_handler = QuestionHandler(
            self._question_client,
            self._issue_filer,
            llm_enabled=self.config.llm_enabled,
            vision_text=self._vision_text,
            tech_env_text=self._tech_env_text,
        )
        self._chat_handler = ChatHandler(
            self._chat_client,
            self.config.project_key,
        )
        self._monitor = Monitor(
            project_key=self.config.project_key,
            review_client=self._review_client,
            question_client=self._question_client,
            notification_client=self._notification_client,
            ws_listener=self._ws_listener,
            issue_filer=self._issue_filer,
            poll_interval=self.config.poll_interval,
            stall_threshold=self.config.stall_threshold,
            logs_client=self._logs_client,
        )
        self._verifier = Verifier(
            workspace_root=self.workspace_root,
            project_key=self.config.project_key,
            issue_filer=self._issue_filer,
        )

    def _all_clients(self) -> list:
        """Return all client instances for cleanup."""
        return [
            c
            for c in [
                self._health_client,
                self._project_client,
                self._review_client,
                self._question_client,
                self._chat_client,
                self._notification_client,
                self._logs_client,
            ]
            if c is not None
        ]

    async def run(self) -> RunReport:
        """Execute the full Rafiki lifecycle. Returns the run report."""
        report: RunReport | None = None
        try:
            # ── INITIALIZING ──
            self._set_state(LifecycleState.INITIALIZING)
            self._load_project_context()
            self._init_clients()
            self._init_handlers()

            # Health check
            healthy = await self._health_client.is_healthy()
            ws_connected = False
            try:
                await self._ws_listener.connect(self.config.ws_url)
                ws_connected = self._ws_listener.connected
            except Exception as exc:
                logger.warning("WebSocket connect failed: %s", exc)

            mode = (
                "auto-approve"
                if self.config.auto_approve
                else (
                    "hybrid (rules + LLM)"
                    if self.config.llm_enabled
                    else "rules-only"
                )
            )
            self._display.banner(
                version=__version__,
                run_id=self.run_id,
                api_url=self.config.api_url,
                api_healthy=healthy,
                ws_url=self.config.ws_url,
                ws_connected=ws_connected,
                project_key=self.config.project_key,
                project_name=self.config.project_name,
                mode=mode,
            )

            if not healthy:
                raise ConnectionError(
                    f"API at {self.config.api_url} is not healthy"
                )

            # ── CREATING PROJECT ──
            self._set_state(LifecycleState.CREATING_PROJECT)
            local_workspace = self.config.resolve_workspace(self.workspace_root)
            docker_workspace = self.config.resolve_docker_workspace(local_workspace)
            logger.info("Creating project: local=%s docker=%s", local_workspace, docker_workspace)
            await self._project_client.create(
                self.config.project_key,
                self.config.project_name,
                docker_workspace,
            )
            self._display.log(
                self._current_state.value,
                f"Created project {self.config.project_key}",
            )

            # Chat: initial status check
            self._set_state(LifecycleState.CHATTING)
            chat_record = await self._chat_handler.on_project_created()
            self.state.chats.append(chat_record)
            self._display.chat(chat_record.prompt, chat_record.response)

            # ── MONITORING LOOP ──
            self._set_state(LifecycleState.MONITORING)
            while not await self._is_complete():
                # Runtime guard
                if self._elapsed_seconds() > self.config.max_runtime:
                    self.state.failed = True
                    log_ctx = await self._fetch_log_context()
                    await self._issue_filer.file_bug(
                        f"Pipeline exceeded max runtime of {self.config.max_runtime / 3600:.1f} hours",
                        "The pipeline did not complete within the allowed time." + log_ctx,
                        priority=0,
                        source="timeout",
                    )
                    break

                events = await self._monitor.poll()

                for event in events:
                    if event.type == "review_gate":
                        issue_id = event.data.get("issue_id", "")
                        self._set_state(LifecycleState.HANDLING_REVIEW)
                        try:
                            detail = await self._review_client.get_detail(issue_id)
                            record = await self._review_handler.handle(detail)
                            self.state.reviews.append(record)
                            # Track artifact paths for cleanup
                            artifact_path = detail.get("artifact_path") or detail.get(
                                "notes", ""
                            )
                            if "artifact:" in str(artifact_path):
                                path = str(artifact_path).split("artifact:")[-1].strip()
                                if path:
                                    self.state.artifact_paths_seen.append(path)
                            self._display.review(record)
                        except Exception as exc:
                            logger.warning("Skipping review %s: %s", issue_id, exc)
                            self._display.log("HANDLING_REVIEW", f"Skipped review {issue_id}: {exc}")
                        self._monitor.mark_review_handled(issue_id)
                        self._set_state(LifecycleState.MONITORING)

                    elif event.type == "question":
                        issue_id = event.data.get("issue_id", "")
                        self._set_state(LifecycleState.HANDLING_QUESTION)
                        try:
                            detail = await self._question_client.get_detail(issue_id)
                            record = await self._question_handler.handle(detail)
                            self.state.questions.append(record)
                            self._display.question(record)
                        except Exception as exc:
                            logger.warning("Skipping question %s: %s", issue_id, exc)
                            self._display.log("HANDLING_QUESTION", f"Skipped question {issue_id}: {exc}")
                        self._monitor.mark_question_handled(issue_id)
                        self._set_state(LifecycleState.MONITORING)

                    elif event.type in ("stage_started", "stage_completed"):
                        title = event.data.get(
                            "title", event.data.get("body", "")
                        )
                        self._display.log(
                            self._current_state.value,
                            f"{event.type.replace('_', ' ').title()}: {title}",
                        )

                # Stall detection
                if self._monitor.is_stalled:
                    self._set_state(LifecycleState.STALLED)
                    stall_issue = await self._monitor.handle_stall()
                    # Chat about the stall
                    chat_record = await self._chat_handler.on_stall(
                        "current stage", self._monitor.stall_minutes
                    )
                    self.state.chats.append(chat_record)
                    self._display.stall(
                        self._monitor.stall_minutes,
                        stall_issue,
                        chat_record.prompt,
                        chat_record.response,
                        self._monitor.stall_count,
                        self.config.max_stalls,
                    )
                    if self._monitor.stall_count > self.config.max_stalls:
                        self.state.failed = True
                        break

                    # Fast-fail: check if pipeline is clearly dead
                    active_agents = await self._get_active_agent_count()
                    fast_fail_reason = self._monitor.should_fast_fail(active_agents)
                    if fast_fail_reason:
                        logger.warning("Fast-fail: %s", fast_fail_reason)
                        self._display.log(
                            "STALLED",
                            f"FAST-FAIL: {fast_fail_reason}",
                        )
                        log_ctx = await self._fetch_log_context()
                        await self._issue_filer.file_bug(
                            "Pipeline is dead -- fast-failing",
                            fast_fail_reason + log_ctx,
                            priority=0,
                            source="monitoring",
                        )
                        self.state.failed = True
                        break

                    self._set_state(LifecycleState.MONITORING)

                await asyncio.sleep(self.config.poll_interval)

            # ── COMPLETED or FAILED ──
            if self.state.failed:
                self._set_state(LifecycleState.FAILED)
            else:
                self._set_state(LifecycleState.COMPLETED)
                # Chat: final status
                chat_record = await self._chat_handler.on_completion()
                self.state.chats.append(chat_record)

            # Sync issues filed into state for report
            self.state.issues_filed = list(self._issue_filer.filed)

            # ── VERIFYING ──
            self._set_state(LifecycleState.VERIFYING)
            verification = await self._verifier.run()
            for check in verification.checks:
                self._display.verification_check(check)

            # ── REPORTING ──
            self._set_state(LifecycleState.REPORTING)
            report = generate_report(self.state, verification, self.config)

        except Exception as exc:
            self._set_state(LifecycleState.FAILED)
            self.state.failed = True
            logger.exception("Unhandled exception in lifecycle")
            log_ctx = await self._fetch_log_context()
            await self._issue_filer.file_bug(
                f"Unhandled exception: {type(exc).__name__}",
                str(exc) + log_ctx,
                priority=0,
                source="lifecycle",
            )
            self.state.issues_filed = list(self._issue_filer.filed)
            verification = VerificationReport(overall="FAIL")
            report = generate_report(self.state, verification, self.config)

        finally:
            # ── CLEANING UP ──
            self._set_state(LifecycleState.CLEANING_UP)
            cleanup_steps = await run_cleanup(
                project_key=self.config.project_key,
                project_client=self._project_client,
                ws_listener=self._ws_listener,
                http_clients=self._all_clients(),
                workspace_root=self.workspace_root,
                generated_source_dir=self.workspace_root
                / self.config.project_key,
                artifact_paths=self.state.artifact_paths_seen,
                run_id=self.run_id,
                skip_cleanup=self.config.skip_cleanup,
                preserve_artifacts=self.config.preserve_artifacts,
                cleanup_timeout=self.config.cleanup_timeout,
                state_data=self.state.model_dump(),
                state_file=self.workspace_root / self.config.state_file,
                report_data=report.model_dump() if report else None,
                report_file=self.workspace_root / self.config.report_file,
            )
            for step in cleanup_steps:
                self._display.cleanup_step(step)

            self._set_state(LifecycleState.DONE)
            self._display.summary_banner(report)

        return report or RunReport(
            run_id=self.run_id, outcome="FAIL", started_at=self.state.started_at
        )

    async def _fetch_log_context(self) -> str:
        """Fetch recent WARNING+ logs from the orchestrator and format as text."""
        if not self._logs_client:
            return ""
        try:
            entries = await self._logs_client.list(level="WARNING", limit=20)
            if not entries:
                return ""
            lines = []
            for e in entries:
                ts = e.get("timestamp", "")
                lvl = e.get("level", "")
                msg = e.get("message", "")
                lines.append(f"[{ts}] {lvl}: {msg}")
            return (
                "\n\n## Recent Orchestrator Logs\n\n```\n"
                + "\n".join(lines)
                + "\n```"
            )
        except Exception as exc:
            logger.debug("Could not fetch orchestrator logs: %s", exc)
            return ""

    async def _get_active_agent_count(self) -> int:
        """Query the API for the number of active agents on this project."""
        try:
            status = await self._project_client.status(self.config.project_key)
            return status.get("active_agents", 0)
        except Exception:
            return -1  # Unknown; don't fast-fail on API errors

    async def _is_complete(self) -> bool:
        """Check if the pipeline is complete."""
        try:
            status = await self._project_client.status(self.config.project_key)
            project_status = status.get("status", "")
            if project_status in ("complete", "completed", "done"):
                return True
        except Exception:
            pass

        # If no new events for completion_timeout, consider done
        if (
            self._monitor
            and self._monitor.seconds_since_activity
            > self.config.completion_timeout
        ):
            # Only if we've handled at least some reviews/questions
            if self.state.reviews or self.state.questions:
                logger.info("Completion timeout reached with no new activity")
                return True

        return False
