"""FileGuard -- validates and executes filesystem write operations."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from orchestrator.lib.bonobo.audit import AuditLog
from orchestrator.lib.scribe.workspace import find_workspace_root

# Maximum file sizes
MAX_ARTIFACT_SIZE = 1_048_576  # 1 MB
MAX_CODE_SIZE = 512_000  # 500 KB

# Directory rules: directory prefix -> allowed extensions
DIRECTORY_RULES: dict[str, set[str]] = {
    "aidlc-docs": {".md"},
    "templates": {".md"},
    "orchestrator": {".py"},
    "tests": {".py"},
    "scripts": {".py", ".sh", ".ps1"},
    "cli": {".py"},
    "dashboard": {".py", ".ts", ".tsx", ".js", ".jsx", ".css", ".html", ".json", ".md"},
    "infra": {".yml", ".yaml", ".dockerfile", ".env", ".sh", ".md", ".toml"},
    "docs": {".md", ".mmd", ".png", ".jpg", ".svg"},
}

# Directories that are completely off-limits for direct writes
FORBIDDEN_DIRECTORIES = {".git", ".beads"}

# Files that must never be deleted
PROTECTED_FILES = {"AGENTS.md", "README.md", ".gitignore"}


@dataclass
class ValidationResult:
    """Result of a path validation check."""

    allowed: bool
    reason: str


class FileGuard:
    """Validates and executes filesystem write operations.

    All file writes by agents flow through this guard.
    """

    def __init__(self, audit: AuditLog, workspace_root: Path | None = None) -> None:
        self._audit = audit
        self._root = workspace_root or find_workspace_root()

    def validate_path(self, path: Path, operation: str = "write") -> ValidationResult:
        """Check whether a path is allowed for the given operation.

        Args:
            path: The target file path (absolute or relative).
            operation: "write", "delete", or "read".

        Returns:
            ValidationResult with allowed flag and reason.
        """
        path = Path(path)

        # Resolve to absolute
        if not path.is_absolute():
            path = (self._root / path).resolve()
        else:
            path = path.resolve()

        # SEC-01: Must be within workspace
        try:
            path.relative_to(self._root)
        except ValueError:
            return ValidationResult(False, f"Path is outside workspace: {path}")

        # SEC-01: No path traversal
        path_str = str(path)
        if "\x00" in path_str:
            return ValidationResult(False, "Path contains null bytes")

        # Get relative path for rule checking
        try:
            relative = path.relative_to(self._root)
        except ValueError:
            return ValidationResult(False, f"Cannot compute relative path: {path}")

        parts = relative.parts
        if not parts:
            return ValidationResult(False, "Empty path")

        # SEC-02: Forbidden directories
        top_dir = parts[0]
        if top_dir in FORBIDDEN_DIRECTORIES:
            return ValidationResult(False, f"Direct writes to {top_dir}/ are forbidden")

        # SEC-02: Hidden files/dirs (except explicitly allowed)
        for part in parts:
            if part.startswith(".") and part not in (".gitkeep",):
                return ValidationResult(False, f"Hidden file/directory not allowed: {part}")

        # SEC-03: File type enforcement
        suffix = path.suffix.lower()
        matched_rule = False
        for dir_prefix, allowed_extensions in DIRECTORY_RULES.items():
            if top_dir == dir_prefix or str(relative).startswith(dir_prefix):
                matched_rule = True
                if suffix not in allowed_extensions:
                    return ValidationResult(
                        False,
                        f"File type '{suffix}' not allowed in {dir_prefix}/. "
                        f"Allowed: {sorted(allowed_extensions)}",
                    )
                break

        # If no rule matched, allow (for top-level config files, etc.)
        if not matched_rule and top_dir not in FORBIDDEN_DIRECTORIES:
            pass  # Allow writes to unregulated directories

        # SEC-04: Size check (only relevant for write, checked at write time)
        # Validation passes -- size checked in write_file()

        return ValidationResult(True, "Path is valid")

    def write_file(
        self,
        path: Path,
        content: str,
        agent: str,
        *,
        overwrite: bool = False,
    ) -> Path:
        """Validated file write.

        Args:
            path: Target file path.
            content: File content to write.
            agent: Name of the requesting agent.
            overwrite: If True, allow overwriting existing files.

        Returns:
            Absolute path to the written file.

        Raises:
            PermissionError: If validation fails.
            FileExistsError: If file exists and overwrite is False.
        """
        path = Path(path)
        if not path.is_absolute():
            path = (self._root / path).resolve()
        else:
            path = path.resolve()

        details = {"path": str(path), "size": len(content), "overwrite": overwrite}

        # Validate
        result = self.validate_path(path, "write")
        if not result.allowed:
            self._audit.log_denied("file", "write_file", agent, result.reason, details)
            raise PermissionError(f"FileGuard denied write: {result.reason}")

        # SEC-04: Size check
        relative = path.relative_to(self._root)
        top_dir = relative.parts[0] if relative.parts else ""
        max_size = MAX_ARTIFACT_SIZE if top_dir in ("aidlc-docs", "docs", "templates") else MAX_CODE_SIZE
        if len(content.encode("utf-8")) > max_size:
            reason = f"File size {len(content)} exceeds limit {max_size} bytes"
            self._audit.log_denied("file", "write_file", agent, reason, details)
            raise PermissionError(f"FileGuard denied write: {reason}")

        # Check existing
        if path.exists() and not overwrite:
            reason = "File already exists and overwrite=False"
            self._audit.log_denied("file", "write_file", agent, reason, details)
            raise FileExistsError(f"File already exists: {path}")

        # REL-01: Atomic write via temp file
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            tmp_fd = tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                prefix=".bonobo_",
                suffix=".tmp",
                delete=False,
            )
            tmp_path = Path(tmp_fd.name)
            try:
                tmp_fd.write(content)
                tmp_fd.close()
                tmp_path.replace(path)
            except Exception:
                tmp_path.unlink(missing_ok=True)
                raise
        except OSError:
            # Fallback: direct write (Windows sometimes has issues with replace)
            path.write_text(content, encoding="utf-8")

        self._audit.log_allowed("file", "write_file", agent, details)
        return path

    def delete_file(self, path: Path, agent: str) -> None:
        """Validated file deletion.

        Args:
            path: Target file path.
            agent: Name of the requesting agent.

        Raises:
            PermissionError: If validation fails or file is protected.
            FileNotFoundError: If file doesn't exist.
        """
        path = Path(path)
        if not path.is_absolute():
            path = (self._root / path).resolve()
        else:
            path = path.resolve()

        details = {"path": str(path)}

        # Validate path
        result = self.validate_path(path, "delete")
        if not result.allowed:
            self._audit.log_denied("file", "delete_file", agent, result.reason, details)
            raise PermissionError(f"FileGuard denied delete: {result.reason}")

        # Check protected files
        if path.name in PROTECTED_FILES:
            reason = f"File is protected: {path.name}"
            self._audit.log_denied("file", "delete_file", agent, reason, details)
            raise PermissionError(f"FileGuard denied delete: {reason}")

        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        path.unlink()
        self._audit.log_allowed("file", "delete_file", agent, details)

    def list_allowed_directories(self) -> dict[str, list[str]]:
        """Return directory write rules.

        Returns:
            Dict mapping directory names to their allowed file extensions.
        """
        return {k: sorted(v) for k, v in DIRECTORY_RULES.items()}
