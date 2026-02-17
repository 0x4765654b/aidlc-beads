"""CLI entry point — python -m rafiki."""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from rafiki import __version__
from rafiki.config import RafikiConfig
from rafiki.lifecycle import LifecycleController


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="rafiki",
        description="Rafiki — Human Simulation Agent for Gorilla Troop acceptance testing.",
    )
    p.add_argument("--version", action="version", version=f"rafiki {__version__}")

    # Connection
    p.add_argument("--api-url", help="Orchestrator API URL (default: http://localhost:9741)")
    p.add_argument("--ws-url", help="WebSocket URL (default: ws://localhost:9741/ws)")

    # Project
    p.add_argument("--project-key", help="Project key (default: sci-calc)")
    p.add_argument("--project-name", help="Project display name")
    p.add_argument("--project-workspace", help="Path to project workspace directory")

    # Decision engine
    p.add_argument("--auto-approve", action="store_true", help="Auto-approve all review gates")
    p.add_argument("--no-llm", action="store_true", help="Disable LLM-based evaluation")
    p.add_argument("--bedrock-model-id", help="Bedrock model ID for LLM evaluation")
    p.add_argument("--aws-profile", help="AWS profile for Bedrock access")

    # Timing
    p.add_argument("--poll-interval", type=float, help="Seconds between polls (default: 5)")
    p.add_argument("--stall-threshold", type=float, help="Seconds before declaring stall (default: 300)")
    p.add_argument("--max-stalls", type=int, help="Max stalls before failing (default: 5)")
    p.add_argument("--max-runtime", type=float, help="Max total runtime in seconds (default: 7200)")
    p.add_argument("--completion-timeout", type=float, help="Quiet seconds before declaring done (default: 120)")

    # Cleanup
    p.add_argument("--skip-cleanup", action="store_true", help="Skip cleanup (for debugging)")
    p.add_argument("--preserve-artifacts", action="store_true", help="Keep AIDLC artifacts after cleanup")

    # Docker path mapping
    p.add_argument("--docker-workspace-root", help="Docker-internal workspace mount (default: /workspace)")
    p.add_argument("--host-workspace-root", help="Host path that maps to docker-workspace-root")

    # Output
    p.add_argument("--state-file", help="State persistence file path")
    p.add_argument("--report-file", help="Report output file path")
    p.add_argument("--log-file", help="Log to file in addition to stdout")
    p.add_argument("--log-format", choices=["text", "json"], help="Log format (default: text)")
    p.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")

    # Resume
    p.add_argument("--resume", action="store_true", help="Resume from saved state file")

    # Config file
    p.add_argument("--config", help="Path to YAML config file")

    return p


def apply_cli_overrides(config: RafikiConfig, args: argparse.Namespace) -> RafikiConfig:
    """Apply CLI arguments to the config, overriding env/defaults."""
    if args.api_url:
        config.api_url = args.api_url
    if args.ws_url:
        config.ws_url = args.ws_url
    if args.project_key:
        config.project_key = args.project_key
    if args.project_name:
        config.project_name = args.project_name
    if args.project_workspace:
        config.project_workspace = args.project_workspace
    if args.auto_approve:
        config.auto_approve = True
    if args.no_llm:
        config.llm_enabled = False
    if args.bedrock_model_id:
        config.bedrock_model_id = args.bedrock_model_id
    if args.aws_profile:
        config.aws_profile = args.aws_profile
    if args.poll_interval is not None:
        config.poll_interval = args.poll_interval
    if args.stall_threshold is not None:
        config.stall_threshold = args.stall_threshold
    if args.max_stalls is not None:
        config.max_stalls = args.max_stalls
    if args.max_runtime is not None:
        config.max_runtime = args.max_runtime
    if args.completion_timeout is not None:
        config.completion_timeout = args.completion_timeout
    if args.docker_workspace_root:
        config.docker_workspace_root = args.docker_workspace_root
    if args.host_workspace_root:
        config.host_workspace_root = args.host_workspace_root
    if args.skip_cleanup:
        config.skip_cleanup = True
    if args.preserve_artifacts:
        config.preserve_artifacts = True
    if args.state_file:
        config.state_file = args.state_file
    if args.report_file:
        config.report_file = args.report_file
    if args.log_file:
        config.log_file = args.log_file
    if args.log_format:
        config.log_format = args.log_format
    if args.verbose:
        config.log_level = "DEBUG"
    return config


def setup_logging(config: RafikiConfig) -> None:
    """Configure Python logging."""
    level = getattr(logging, config.log_level.upper(), logging.INFO)

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if config.log_file:
        handlers.append(logging.FileHandler(config.log_file, encoding="utf-8"))

    if config.log_format == "json":
        fmt = "%(message)s"
    else:
        fmt = "%(asctime)s %(name)-24s %(levelname)-5s %(message)s"

    logging.basicConfig(level=level, format=fmt, handlers=handlers, force=True)


def detect_workspace_root() -> Path:
    """Find the repository root by walking up from CWD looking for .beads/ or .git/."""
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / ".beads").exists() or (parent / ".git").exists():
            return parent
    return cwd


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # Build config: defaults + env → CLI overrides
    config = RafikiConfig()
    config = apply_cli_overrides(config, args)
    setup_logging(config)

    workspace_root = detect_workspace_root()
    logger = logging.getLogger("rafiki")
    logger.info("Workspace root: %s", workspace_root)

    # Run the lifecycle
    controller = LifecycleController(config, workspace_root)

    try:
        report = asyncio.run(controller.run())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(130)

    # Exit code: 0 for PASS, 1 for FAIL
    sys.exit(0 if report.outcome == "PASS" else 1)


if __name__ == "__main__":
    main()
