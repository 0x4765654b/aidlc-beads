<!-- beads-issue: gt-29 -->
<!-- beads-review: gt-30 -->
# Functional Design -- Unit 3: Bonobo Write Guards

## Overview

Bonobo is the **privileged operation gatekeeper** for Gorilla Troop. Every write operation -- filesystem, Git, Beads state -- is validated and audited through a guard before execution. No agent writes directly; all writes flow through Bonobo.

**Module path**: `orchestrator/lib/bonobo/`

Three guard modules:
1. **FileGuard** -- validates and executes filesystem writes
2. **GitGuard** -- manages branches, commits, merges
3. **BeadsGuard** -- validates Beads issue operations

All guards share a common audit log mechanism.

---

## Shared: Audit Log

```python
@dataclass
class AuditEntry:
    timestamp: datetime
    guard: str              # "file", "git", "beads"
    operation: str          # "write_file", "commit", "create_issue", etc.
    agent: str              # Which agent requested the operation
    details: dict           # Operation-specific details
    result: str             # "allowed", "denied", "error"
    reason: str | None      # Denial or error reason

class AuditLog:
    """Append-only audit trail for all privileged operations."""
    
    def log(self, entry: AuditEntry) -> None:
        """Append an entry. Writes to both in-memory buffer and Agent Mail #ops thread."""
    
    def recent(self, limit: int = 50) -> list[AuditEntry]:
        """Get recent entries."""
    
    def filter_by_agent(self, agent: str) -> list[AuditEntry]:
        """Get entries for a specific agent."""
```

The audit log writes to:
1. An in-memory ring buffer (last 1000 entries)
2. Agent Mail `#ops` thread (persistent, via `agent_mail.client`)

---

## Module: `file_guard.py` -- Filesystem Write Guard

### `validate_path(path: Path, operation: str) -> ValidationResult`

Check whether a path is allowed for the given operation.

**Rules**:
1. All paths must be within the workspace root
2. `aidlc-docs/` -- only `.md` files allowed, no executable code
3. `orchestrator/` -- only `.py` files allowed
4. `tests/` -- only `.py` files allowed
5. `.beads/` -- DENY all direct writes (use BeadsGuard)
6. `.git/` -- DENY all direct writes (use GitGuard)
7. `templates/` -- only `.md` files allowed
8. No writes to hidden files/dirs (starting with `.`) except explicitly allowed
9. File names must not contain `..` (path traversal)
10. Maximum file size: 1MB for artifacts, 500KB for code

**Returns**: `ValidationResult` with `allowed: bool`, `reason: str`

### `write_file(path: Path, content: str, agent: str, *, overwrite: bool = False) -> Path`

Validated file write.

**Business Rules**:
1. Call `validate_path()` first -- deny if invalid
2. If file exists and `overwrite=False`, raise `FileExistsError`
3. Create parent directories as needed
4. Write file with UTF-8 encoding
5. Log to audit trail: agent, path, size, overwrite flag
6. Return the absolute path

### `delete_file(path: Path, agent: str) -> None`

Validated file deletion.

**Business Rules**:
1. Validate path is within workspace
2. DENY deletion of any file in `.beads/`, `.git/`, `AGENTS.md`, `README.md`
3. Log to audit trail
4. Delete the file

### `list_allowed_directories() -> list[str]`

Return the list of directories agents are allowed to write to, with their file type restrictions.

---

## Module: `git_guard.py` -- Git Operations Guard

### Configuration

```python
AIDLC_BRANCH_PREFIX = "aidlc/"
PROTECTED_BRANCHES = ["main", "master", "develop"]
COMMIT_MESSAGE_PATTERN = re.compile(r"^\[[\w-]+\]\s.+")  # e.g., "[gt-17] Add functional design"
```

### `create_branch(branch_name: str, agent: str, base: str = "main") -> str`

Create a new Git branch.

**Rules**:
1. Agent branches must use `aidlc/` prefix (e.g., `aidlc/unit-1-scribe`)
2. Branch name validated: lowercase, alphanumeric, hyphens, slashes only
3. Base branch must exist
4. Audit log entry
5. Returns the branch name

### `checkout_branch(branch_name: str, agent: str) -> None`

Switch to a branch.

**Rules**:
1. Branch must exist
2. Working tree must be clean (no uncommitted changes)
3. Audit log entry

### `commit(message: str, files: list[Path], agent: str, issue_id: str) -> str`

Create a Git commit.

**Rules**:
1. Message must match `COMMIT_MESSAGE_PATTERN`: `[issue-id] description`
2. If message doesn't include issue ID, prepend it: `[{issue_id}] {message}`
3. All files must pass `validate_path()`
4. Stage only the specified files (no `git add .`)
5. No commits to protected branches (main, master, develop)
6. Audit log entry with commit hash, files, message
7. Returns the commit hash

### `merge(source: str, target: str, agent: str, strategy: str = "merge") -> MergeResult`

Merge one branch into another.

```python
@dataclass
class MergeResult:
    success: bool
    commit_hash: str | None
    conflicts: list[str]       # Conflicting file paths
    strategy_used: str
```

**Rules**:
1. Target must not be a protected branch (agents can't merge to main directly)
2. Source branch must exist
3. If conflicts occur, report them in `MergeResult` (don't auto-resolve)
4. Audit log entry

### `get_status(agent: str) -> GitStatus`

Get current Git status.

```python
@dataclass
class GitStatus:
    branch: str
    clean: bool
    staged: list[str]
    modified: list[str]
    untracked: list[str]
```

### `get_diff(path: Path | None = None) -> str`

Get diff output (optionally for a specific file).

---

## Module: `beads_guard.py` -- Beads Operations Guard

### `validate_create(title: str, issue_type: str, labels: list[str], agent: str) -> ValidationResult`

Validate a Beads issue creation request.

**Rules**:
1. Title must not be empty
2. `issue_type` must be one of: task, epic, bug, feature, chore, decision, message
3. Labels must follow conventions: `phase:{name}`, `unit:{name}`, `stage:{name}`, `type:{name}`
4. Agents cannot create epics (only Harmbe/ProjectMinder can)
5. Q&A issues (`type: message`) must have `--assignee human`

### `validate_update(issue_id: str, changes: dict, agent: str) -> ValidationResult`

Validate a Beads issue update request.

**Rules**:
1. Issue must exist
2. Agents can only update issues assigned to them (or unassigned)
3. Cannot change issue type after creation
4. Cannot remove `phase:` labels
5. Status transitions must be valid: open -> in_progress -> done, or any -> closed

### `validate_dependency(blocked_id: str, blocker_id: str, dep_type: str, agent: str) -> ValidationResult`

Validate a dependency addition.

**Rules**:
1. Both issues must exist
2. Adding dependency must not create a cycle (call `bd dep cycles` to check)
3. `parent` type dependencies: child must not already have a different parent
4. Audit log entry

### `guarded_create(title, issue_type, priority, agent, **kwargs) -> BeadsIssue`

Validated issue creation: validate first, then delegate to `beads.client.create_issue()`.

### `guarded_update(issue_id, agent, **kwargs) -> None`

Validated issue update: validate first, then delegate to `beads.client.update_issue()`.

### `guarded_close(issue_id, agent, reason=None) -> None`

Validated issue close: check that agent is allowed, then delegate.

---

## Error Handling

| Guard | Error | Behavior |
|-------|-------|----------|
| FileGuard | Path outside workspace | Deny + audit "denied" |
| FileGuard | Wrong file type for directory | Deny + audit "denied" |
| FileGuard | Path traversal attempt | Deny + audit "denied" + alert |
| GitGuard | Commit to protected branch | Deny + audit "denied" |
| GitGuard | Malformed commit message | Deny + audit "denied" |
| GitGuard | Merge conflicts | Return MergeResult with conflicts |
| BeadsGuard | Invalid issue type/labels | Deny + audit "denied" |
| BeadsGuard | Cycle would be created | Deny + audit "denied" |
| All | Unexpected exception | Audit "error" + re-raise |

All denials are logged but do NOT raise exceptions by default -- they return `ValidationResult` with `allowed=False`. The `guarded_*` convenience functions raise `PermissionError` on denial.

---

## Dependencies

- **Internal**: `orchestrator.lib.beads.client`, `orchestrator.lib.agent_mail.client`
- **Python stdlib**: `subprocess` (git), `pathlib`, `re`, `dataclasses`, `datetime`
- **External**: None
- **System**: `git` on PATH
