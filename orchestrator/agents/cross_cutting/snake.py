"""Snake -- security validation agent."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from orchestrator.agents.base import BaseAgent
from orchestrator.lib.context.dispatch import (
    DispatchMessage,
    CompletionMessage,
    build_completion,
)
from orchestrator.lib.scribe import create_artifact

logger = logging.getLogger("agents.snake")

# Security check categories
SECURITY_CATEGORIES = [
    "dependency_vulnerabilities",
    "hardcoded_secrets",
    "owasp_issues",
    "insecure_configurations",
    "injection_risks",
]


class Snake(BaseAgent):
    """Security scanning agent invoked at specific AIDLC checkpoints.

    Checkpoints:
    - After NFR Design (if executed)
    - After Code Generation (always)
    - During Build and Test (security test validation)

    Scans for: security gaps, dependency vulnerabilities,
    hardcoded secrets, OWASP compliance issues.
    """

    agent_type = "Snake"
    agent_mail_identity = "Snake"

    system_prompt = (
        "You are Snake, the security scanning agent for the Gorilla Troop "
        "orchestration system. You review artifacts and code for security "
        "vulnerabilities. You are thorough, precise, and never skip a check.\n\n"
        "For each scan, analyse the provided content and respond with a JSON "
        "object containing:\n"
        '- "findings": a list of finding objects, each with:\n'
        '    - "category": one of dependency_vulnerabilities, hardcoded_secrets, '
        "owasp_issues, insecure_configurations, injection_risks\n"
        '    - "severity": "critical", "high", "medium", or "low"\n'
        '    - "title": short description\n'
        '    - "description": detailed explanation\n'
        '    - "location": file path and line/section if applicable\n'
        '    - "recommendation": how to fix\n'
        '- "summary": overall security assessment\n'
        '- "passed": true if no critical or high findings, false otherwise'
    )

    async def _execute(self, dispatch: DispatchMessage) -> CompletionMessage:
        """Perform security scanning on artifacts and code.

        Expects dispatch.instructions to be a JSON string with:
            stage_name: str -- the AIDLC stage being scanned
            artifact_paths: list[str] -- paths to artifact files to scan
            code_paths: list[str] -- paths to code files to scan
        """
        logger.info(
            "[Snake] Starting security scan for stage='%s' issue='%s'",
            dispatch.stage_name,
            dispatch.beads_issue_id,
        )

        # ------------------------------------------------------------------
        # 1. Parse scan request
        # ------------------------------------------------------------------
        scan_ctx = _parse_scan_context(dispatch)
        stage_name = scan_ctx.get("stage_name", dispatch.stage_name)
        artifact_paths = scan_ctx.get("artifact_paths", [])
        code_paths = scan_ctx.get("code_paths", [])

        # Also include input_artifacts from the dispatch itself
        all_artifact_paths = list(set(artifact_paths + dispatch.input_artifacts))
        all_code_paths = list(set(code_paths))

        if not all_artifact_paths and not all_code_paths:
            logger.warning("[Snake] No files provided for security scan")
            return build_completion(
                stage_name=dispatch.stage_name,
                beads_issue_id=dispatch.beads_issue_id,
                output_artifacts=[],
                summary="No files provided for security scan.",
                status="completed",
            )

        # ------------------------------------------------------------------
        # 2. Read all target files
        # ------------------------------------------------------------------
        file_contents: list[str] = []

        for rel_path in all_artifact_paths:
            content = _safe_read_file(dispatch.workspace_root, rel_path)
            file_contents.append(
                f"## Artifact: {rel_path}\n```\n{content}\n```"
            )

        for rel_path in all_code_paths:
            content = _safe_read_file(dispatch.workspace_root, rel_path)
            file_contents.append(
                f"## Code: {rel_path}\n```\n{content}\n```"
            )

        combined_content = "\n\n".join(file_contents)
        logger.info(
            "[Snake] Loaded %d artifact(s) and %d code file(s) (%d chars total)",
            len(all_artifact_paths),
            len(all_code_paths),
            len(combined_content),
        )

        # ------------------------------------------------------------------
        # 3. Build security analysis prompt and invoke LLM
        # ------------------------------------------------------------------
        prompt = (
            f"Perform a security review of the following files from the "
            f"'{stage_name}' stage.\n\n"
            f"Check for:\n"
            f"1. **Dependency vulnerabilities** -- known CVEs, outdated packages\n"
            f"2. **Hardcoded secrets** -- API keys, passwords, tokens in code/config\n"
            f"3. **OWASP issues** -- injection, XSS, CSRF, broken auth, etc.\n"
            f"4. **Insecure configurations** -- overly permissive IAM, open ports\n"
            f"5. **Injection risks** -- SQL injection, command injection, SSRF\n\n"
            f"{combined_content}\n\n"
            f"Respond with a JSON object containing your findings as specified "
            f"in your system prompt."
        )

        llm_response = await self._invoke_llm(prompt)
        logger.info(
            "[Snake] LLM security analysis received (%d chars)",
            len(llm_response),
        )

        # ------------------------------------------------------------------
        # 4. Parse findings from LLM response
        # ------------------------------------------------------------------
        analysis = _parse_security_analysis(llm_response)
        findings = analysis.get("findings", [])
        summary_text = analysis.get("summary", "Security scan completed.")
        passed = analysis.get("passed", True)

        critical_count = sum(
            1 for f in findings if f.get("severity") in ("critical", "high")
        )
        total_count = len(findings)

        logger.info(
            "[Snake] Scan results: %d findings (%d critical/high), passed=%s",
            total_count,
            critical_count,
            passed,
        )

        # ------------------------------------------------------------------
        # 5. Generate security report artifact
        # ------------------------------------------------------------------
        report_content = _build_report_markdown(
            stage_name, findings, summary_text, passed
        )

        output_artifacts: list[str] = []
        try:
            report_path = create_artifact(
                stage=_sanitize_stage_name(stage_name),
                name="security-scan",
                content=report_content,
                beads_issue_id=dispatch.beads_issue_id,
                review_gate_id=dispatch.review_gate_id,
                phase=dispatch.phase,
            )
            output_artifacts.append(str(report_path))
            logger.info("[Snake] Security report artifact created: %s", report_path)
        except FileExistsError:
            # Report already exists -- this may be a re-scan
            logger.info(
                "[Snake] Security report artifact already exists, skipping creation"
            )
        except Exception as exc:
            logger.warning(
                "[Snake] Failed to create security report artifact: %s", exc
            )

        # ------------------------------------------------------------------
        # 6. Return completion
        # ------------------------------------------------------------------
        status = "completed" if passed else "needs_rework"
        completion_summary = (
            f"Security scan for '{stage_name}': {total_count} finding(s), "
            f"{critical_count} critical/high. "
            f"{'PASSED' if passed else 'FAILED -- rework required'}. "
            f"{summary_text}"
        )

        return build_completion(
            stage_name=dispatch.stage_name,
            beads_issue_id=dispatch.beads_issue_id,
            output_artifacts=output_artifacts,
            summary=completion_summary,
            status=status,
            rework_reason=(
                f"{critical_count} critical/high security findings"
                if not passed
                else None
            ),
        )


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _parse_scan_context(dispatch: DispatchMessage) -> dict:
    """Extract scan context from dispatch instructions."""
    if not dispatch.instructions:
        return {}
    try:
        data = json.loads(dispatch.instructions)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, TypeError):
        pass
    return {}


def _safe_read_file(workspace_root: str, rel_path: str) -> str:
    """Read a file safely, returning error text on failure."""
    full_path = Path(workspace_root) / rel_path
    if not full_path.exists():
        return f"(file not found: {rel_path})"
    if not full_path.is_file():
        return f"(not a file: {rel_path})"
    try:
        content = full_path.read_text(encoding="utf-8")
        # Truncate very large files to keep the LLM prompt manageable
        if len(content) > 50_000:
            return content[:50_000] + f"\n... (truncated, {len(content)} chars total)"
        return content
    except Exception as exc:
        return f"(read error: {exc})"


def _parse_security_analysis(response: str) -> dict:
    """Extract JSON analysis from the LLM response.

    Falls back to a minimal result if parsing fails.
    """
    try:
        start = response.index("{")
        depth = 0
        for i in range(start, len(response)):
            if response[i] == "{":
                depth += 1
            elif response[i] == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(response[start : i + 1])
    except (ValueError, json.JSONDecodeError):
        pass

    logger.warning(
        "[Snake] Could not parse JSON from LLM response, treating as pass"
    )
    return {
        "findings": [],
        "summary": "LLM response could not be parsed. Manual review recommended.",
        "passed": True,
    }


def _build_report_markdown(
    stage_name: str,
    findings: list[dict],
    summary: str,
    passed: bool,
) -> str:
    """Build a markdown security report from parsed findings."""
    lines = [
        f"# Security Scan Report: {stage_name}\n",
        f"**Result**: {'PASSED' if passed else 'FAILED'}\n",
        f"**Findings**: {len(findings)}\n",
        f"\n## Summary\n\n{summary}\n",
    ]

    if findings:
        lines.append("\n## Findings\n")
        for i, finding in enumerate(findings, 1):
            severity = finding.get("severity", "unknown").upper()
            title = finding.get("title", "Untitled finding")
            description = finding.get("description", "")
            location = finding.get("location", "N/A")
            category = finding.get("category", "unknown")
            recommendation = finding.get("recommendation", "")

            lines.append(f"### {i}. [{severity}] {title}\n")
            lines.append(f"- **Category**: {category}")
            lines.append(f"- **Severity**: {severity}")
            lines.append(f"- **Location**: {location}")
            lines.append(f"- **Description**: {description}")
            if recommendation:
                lines.append(f"- **Recommendation**: {recommendation}")
            lines.append("")
    else:
        lines.append("\n## Findings\n\nNo security issues detected.\n")

    return "\n".join(lines)


def _sanitize_stage_name(stage_name: str) -> str:
    """Sanitize a stage name for use as a directory name.

    Converts to lowercase, replaces spaces/underscores with hyphens,
    removes non-alphanumeric characters except hyphens.
    """
    import re

    sanitized = stage_name.lower().strip()
    sanitized = re.sub(r"[\s_]+", "-", sanitized)
    sanitized = re.sub(r"[^a-z0-9\-]", "", sanitized)
    sanitized = re.sub(r"-+", "-", sanitized)
    sanitized = sanitized.strip("-")
    return sanitized or "security-scan"
