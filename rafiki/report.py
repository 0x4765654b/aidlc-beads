"""Run report generator — produces the structured JSON report."""
from __future__ import annotations

from datetime import datetime, timezone

from rafiki.config import RafikiConfig
from rafiki.models import RafikiState, RunReport, VerificationReport


def generate_report(
    state: RafikiState,
    verification: VerificationReport,
    config: RafikiConfig,
) -> RunReport:
    """Generate a RunReport from the accumulated state and verification results."""
    now = datetime.now(timezone.utc).isoformat()
    started = state.started_at or now

    # Calculate duration
    try:
        start_dt = datetime.fromisoformat(started)
        end_dt = datetime.fromisoformat(now)
        duration = (end_dt - start_dt).total_seconds()
    except (ValueError, TypeError):
        duration = 0.0

    # Determine outcome
    verification_pass = verification.overall == "PASS"
    outcome = "FAIL" if state.failed or not verification_pass else "PASS"
    if outcome == "PASS" and state.issues_filed:
        outcome = "PASS"  # Still PASS, but issues are noted in the report

    return RunReport(
        run_id=state.run_id,
        started_at=started,
        completed_at=now,
        duration_seconds=duration,
        project_key=config.project_key,
        outcome=outcome,
        lifecycle_states=state.state_transitions,
        reviews_handled=state.reviews,
        questions_answered=state.questions,
        chat_interactions=state.chats,
        stalls_detected=state.stall_count,
        issues_filed=state.issues_filed,
        issues_filed_count=len(state.issues_filed),
        verification=verification,
    )
