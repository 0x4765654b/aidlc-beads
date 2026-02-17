"""Post-run cleanup — removes the simulated project and its artifacts."""
from __future__ import annotations

import asyncio
import logging
import shutil
from pathlib import Path

logger = logging.getLogger("rafiki.cleanup")


async def run_cleanup(
    *,
    project_key: str,
    project_client,          # ProjectClient
    ws_listener,             # WebSocketListener | None
    http_clients: list,      # list of BaseClient instances to close
    workspace_root: Path,
    generated_source_dir: Path | None = None,
    artifact_paths: list[str] | None = None,
    run_id: str = "",
    skip_cleanup: bool = False,
    preserve_artifacts: bool = False,
    cleanup_timeout: float = 60.0,
    state_data: dict | None = None,
    state_file: Path | None = None,
    report_data: dict | None = None,
    report_file: Path | None = None,
) -> list[str]:
    """Execute cleanup steps. Returns a list of step descriptions for logging."""
    steps: list[str] = []

    if skip_cleanup:
        logger.warning("Cleanup skipped (--skip-cleanup)")
        steps.append("SKIPPED: cleanup disabled by --skip-cleanup")
        # Still persist state and report
        _persist_json(state_data, state_file, steps, "state")
        _persist_json(report_data, report_file, steps, "report")
        return steps

    try:
        await asyncio.wait_for(
            _do_cleanup(
                project_key=project_key,
                project_client=project_client,
                ws_listener=ws_listener,
                http_clients=http_clients,
                workspace_root=workspace_root,
                generated_source_dir=generated_source_dir,
                artifact_paths=artifact_paths,
                run_id=run_id,
                preserve_artifacts=preserve_artifacts,
                state_data=state_data,
                state_file=state_file,
                report_data=report_data,
                report_file=report_file,
                steps=steps,
            ),
            timeout=cleanup_timeout,
        )
    except asyncio.TimeoutError:
        logger.error("Cleanup timed out after %.0fs", cleanup_timeout)
        steps.append(f"TIMEOUT: cleanup exceeded {cleanup_timeout}s limit")
    except Exception as exc:
        logger.error("Cleanup error: %s", exc)
        steps.append(f"ERROR: {exc}")

    return steps


async def _do_cleanup(
    *,
    project_key: str,
    project_client,
    ws_listener,
    http_clients: list,
    workspace_root: Path,
    generated_source_dir: Path | None,
    artifact_paths: list[str] | None,
    run_id: str,
    preserve_artifacts: bool,
    state_data: dict | None,
    state_file: Path | None,
    report_data: dict | None,
    report_file: Path | None,
    steps: list[str],
) -> None:
    """Execute the actual cleanup steps in order."""

    # 1. Close WebSocket
    if ws_listener is not None:
        try:
            await ws_listener.close()
            steps.append("Closed WebSocket connection")
            logger.info("Closed WebSocket connection")
        except Exception as exc:
            steps.append(f"WebSocket close failed: {exc}")
            logger.warning("WebSocket close failed: %s", exc)

    # 2. Delete simulated project from API
    try:
        await project_client.delete(project_key)
        steps.append(f"Deleted project {project_key} from registry")
        logger.info("Deleted project %s from registry", project_key)
    except Exception as exc:
        steps.append(f"Project delete failed: {exc}")
        logger.warning("Failed to delete project %s: %s", project_key, exc)

    # 3. Remove generated source files
    if generated_source_dir and generated_source_dir.exists():
        if _is_safe_path(generated_source_dir, workspace_root):
            try:
                shutil.rmtree(generated_source_dir)
                steps.append(f"Removed generated source: {generated_source_dir}")
                logger.info("Removed generated source: %s", generated_source_dir)
            except Exception as exc:
                steps.append(f"Source removal failed: {exc}")
                logger.warning("Failed to remove %s: %s", generated_source_dir, exc)
        else:
            steps.append(f"SKIPPED source removal: {generated_source_dir} outside workspace")
            logger.warning("Refusing to delete %s -- outside workspace root", generated_source_dir)

    # 4. Remove AIDLC artifacts
    if not preserve_artifacts and artifact_paths:
        removed = 0
        for rel_path in artifact_paths:
            full_path = workspace_root / rel_path
            if full_path.exists() and _is_safe_path(full_path, workspace_root):
                try:
                    if full_path.is_dir():
                        shutil.rmtree(full_path)
                    else:
                        full_path.unlink()
                    removed += 1
                except Exception as exc:
                    logger.warning("Failed to remove artifact %s: %s", rel_path, exc)
        steps.append(f"Removed {removed} AIDLC artifacts")
        logger.info("Removed %d AIDLC artifacts", removed)
    elif preserve_artifacts:
        steps.append("Preserved AIDLC artifacts (--preserve-artifacts)")

    # 5. Close pipeline Beads issues (not Rafiki-filed issues)
    await _close_pipeline_issues(workspace_root, run_id, steps)

    # 6. Persist final state and report
    _persist_json(state_data, state_file, steps, "state")
    _persist_json(report_data, report_file, steps, "report")

    # 7. Close HTTP clients
    for client in http_clients:
        try:
            await client.close()
        except Exception:
            pass
    steps.append(f"Closed {len(http_clients)} HTTP client(s)")
    logger.info("Closed %d HTTP client(s)", len(http_clients))


def _is_safe_path(target: Path, workspace_root: Path) -> bool:
    """Ensure target is under workspace_root to prevent accidental deletions."""
    try:
        target.resolve().relative_to(workspace_root.resolve())
        return True
    except ValueError:
        return False


async def _close_pipeline_issues(workspace_root: Path, run_id: str, steps: list[str]) -> None:
    """Close Beads issues created by the simulated pipeline (not by Rafiki itself).

    Only closes issues that were tagged with this run's label by the AIDLC
    pipeline. Issues filed by Rafiki (discovered-by:rafiki) are preserved
    because they represent real findings to fix.

    If no run_id-scoped issues exist, skips closing entirely to avoid
    accidentally closing unrelated project issues.
    """
    if not run_id:
        steps.append("No run_id -- skipping pipeline issue cleanup")
        return

    from rafiki.issues import _run_bd
    import json

    # Only close issues that belong to this specific Rafiki run AND were
    # created by the pipeline (not by Rafiki itself).
    # Safety: list issues with the run label, then filter out Rafiki-filed ones.
    result = await _run_bd(
        ["list", "--status", "open", "--label", f"rafiki-run:{run_id}", "--json"],
        cwd=workspace_root,
    )
    if not result:
        steps.append("No pipeline issues from this run to close")
        return

    try:
        issues = json.loads(result)
        if isinstance(issues, dict):
            issues = issues.get("issues", [])
    except json.JSONDecodeError:
        steps.append("Could not parse issue list for cleanup")
        return

    closed_count = 0
    preserved_count = 0
    for issue in issues:
        labels = issue.get("labels", [])
        issue_id = issue.get("id", "")
        if not issue_id:
            continue
        # Preserve issues filed by Rafiki -- those are real findings
        if "discovered-by:rafiki" in labels:
            preserved_count += 1
            continue
        await _run_bd(
            ["close", issue_id, "--reason", "Closed by Rafiki cleanup -- simulation complete."],
            cwd=workspace_root,
        )
        closed_count += 1

    msg = f"Closed {closed_count} pipeline Beads issues"
    if preserved_count:
        msg += f" (preserved {preserved_count} Rafiki-filed issues)"
    steps.append(msg)
    logger.info(msg)


def _persist_json(data: dict | None, filepath: Path | None, steps: list[str], label: str) -> None:
    """Write a dict to a JSON file."""
    if data is not None and filepath is not None:
        import json
        try:
            filepath.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
            steps.append(f"Persisted {label}: {filepath}")
            logger.info("Persisted %s: %s", label, filepath)
        except Exception as exc:
            steps.append(f"Failed to persist {label}: {exc}")
            logger.warning("Failed to persist %s: %s", label, exc)
