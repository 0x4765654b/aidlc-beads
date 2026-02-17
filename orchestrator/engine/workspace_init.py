"""Workspace initialization -- create and scaffold a project workspace.

Called by the project-creation route when the workspace directory does not
yet exist.  Idempotent: safe to call on an already-initialized workspace.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger("engine.workspace_init")

# Directories created under aidlc-docs/ for the standard AIDLC scaffold.
_AIDLC_DIRS = [
    "aidlc-docs/inception/requirements",
    "aidlc-docs/inception/plans",
    "aidlc-docs/inception/reverse-engineering",
    "aidlc-docs/inception/user-stories",
    "aidlc-docs/inception/design",
    "aidlc-docs/construction",
]


def initialize_workspace(workspace_path: Path, project_key: str) -> None:
    """Create *workspace_path* and bootstrap it for the AIDLC pipeline.

    Steps:
        1. ``mkdir -p`` the workspace directory.
        2. Run ``bd init`` to create ``.beads/`` (skipped if already present).
        3. Create the ``aidlc-docs/`` skeleton directories.
        4. Copy seed docs (``vision.md``, ``tech-env.md``) if found nearby.

    Raises:
        OSError:  If the directory cannot be created.
        RuntimeError:  If ``bd`` is not on PATH.
        subprocess.CalledProcessError:  If ``bd init`` fails.
    """
    # 1. Create the workspace directory tree.
    workspace_path.mkdir(parents=True, exist_ok=True)
    logger.info("[INIT] Created workspace directory: %s", workspace_path)

    # 2. Initialize Beads (.beads/) -- required for find_workspace_root().
    beads_dir = workspace_path / ".beads"
    if not beads_dir.is_dir():
        _run_bd_init(workspace_path, project_key)
    else:
        logger.info("[INIT] .beads/ already exists, skipping bd init")

    # 3. Scaffold aidlc-docs/ directories.
    for relpath in _AIDLC_DIRS:
        (workspace_path / relpath).mkdir(parents=True, exist_ok=True)
    logger.info("[INIT] Scaffolded aidlc-docs/ skeleton")

    # 4. Copy seed documents if available nearby.
    _copy_seed_docs(workspace_path)


def _run_bd_init(workspace_path: Path, project_key: str) -> None:
    """Run ``bd init --prefix <key> --no-db --quiet`` inside *workspace_path*."""
    cmd = ["bd", "init", "--prefix", project_key, "--no-db", "--quiet"]
    try:
        subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            cwd=str(workspace_path),
        )
    except FileNotFoundError:
        raise RuntimeError(
            "Beads CLI (bd) not found on PATH. "
            "Install Beads: https://github.com/steveyegge/beads"
        ) from None
    logger.info("[INIT] Ran bd init in %s (prefix=%s)", workspace_path, project_key)


def _copy_seed_docs(workspace_path: Path) -> None:
    """Copy vision.md / tech-env.md from a parent or sibling location, if found."""
    seed_files = ["vision.md", "tech-env.md"]
    search_dirs = [workspace_path.parent, *workspace_path.parent.iterdir()]

    for name in seed_files:
        # Already present in the workspace -- skip.
        dest = workspace_path / name
        if dest.exists():
            continue

        for candidate_dir in search_dirs:
            if not candidate_dir.is_dir():
                continue
            src = candidate_dir / name
            if src.is_file():
                dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
                logger.info("[INIT] Copied seed doc %s from %s", name, src)
                break
