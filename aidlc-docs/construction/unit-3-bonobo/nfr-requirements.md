<!-- beads-issue: gt-31 -->
<!-- beads-review: gt-32 -->
# NFR Requirements -- Unit 3: Bonobo Write Guards

## Security Requirements

### SEC-01: Path Traversal Prevention
- All file paths MUST be resolved to absolute paths and verified to be within the workspace root
- Any path containing `..`, symbolic links escaping workspace, or null bytes MUST be rejected
- **Test**: Attempt writes with `../../etc/passwd`, `symlink-escape`, `null\x00byte`

### SEC-02: Directory Isolation
- Agents MUST NOT write to directories outside their scope
- `.git/` internal files are off-limits (only GitGuard's `subprocess` calls touch Git)
- `.beads/` internal files are off-limits (only BeadsGuard via `bd` CLI touches Beads)
- Hidden files/directories (`.env`, `.secrets`, etc.) are DENIED by default
- **Test**: Attempt write to `.git/config`, `.beads/issues.jsonl`, `.env`

### SEC-03: File Type Enforcement
- `aidlc-docs/` accepts ONLY `.md` files -- no `.py`, `.sh`, `.exe`, `.js`
- `orchestrator/` accepts ONLY `.py` files
- `tests/` accepts ONLY `.py` files
- `templates/` accepts ONLY `.md` files
- **Rationale**: Prevents code injection into documentation directories
- **Test**: Attempt writing `aidlc-docs/evil.py`, `templates/run.sh`

### SEC-04: No Silent Overwrites
- File writes MUST NOT silently overwrite existing files unless `overwrite=True` is explicitly passed
- **Rationale**: Prevents accidental artifact destruction
- **Test**: Write file, then write again without overwrite flag

### SEC-05: Protected Branch Enforcement
- Agents MUST NOT commit directly to `main`, `master`, or `develop`
- All agent work MUST be on `aidlc/*` prefixed branches
- Merge to protected branches requires human approval (routed through Harmbe)
- **Test**: Attempt commit on `main`, attempt merge to `main`

### SEC-06: Commit Message Integrity
- All commit messages MUST reference a Beads issue ID: `[gt-XX] description`
- Messages without issue references are DENIED
- **Rationale**: Ensures traceability from code to workflow state
- **Test**: Commit with bare message, commit with `[gt-5] message`

### SEC-07: Beads State Integrity
- Issue type cannot be changed after creation
- Phase labels cannot be removed
- Status transitions follow the defined state machine: open -> in_progress -> done
- Circular dependencies MUST be detected and rejected before creation
- **Test**: Attempt invalid transition, attempt cycle creation

### SEC-08: Agent Permission Boundaries
- Agents can only update issues they own (assigned to them) or unassigned issues
- Only Harmbe and ProjectMinder can create epics
- Q&A issues must be assigned to `human`
- **Test**: Agent A tries to update Agent B's issue

## Audit Requirements

### AUD-01: Complete Audit Trail
- Every write operation (file, git, beads) MUST produce an audit entry
- Entries include: timestamp, guard, operation, agent, details, result, reason
- Both allowed and denied operations are logged
- **Storage**: In-memory ring buffer (1000 entries) + Agent Mail #ops thread

### AUD-02: Denial Alerting
- Path traversal attempts MUST trigger high-priority alerts (not just log entries)
- Three or more denials from the same agent in 5 minutes MUST trigger an alert
- Alerts are routed to Harmbe for human notification
- **Test**: Trigger path traversal, verify alert generated

### AUD-03: Audit Immutability
- Audit entries MUST be append-only -- no deletion or modification
- The Agent Mail #ops thread serves as the tamper-evident persistent store

## Reliability Requirements

### REL-01: Atomic File Writes
- File writes SHOULD use write-to-temp-then-rename pattern to prevent partial writes on crash
- If the temp write fails, the original file MUST remain unchanged

### REL-02: Git Operation Safety
- Git operations that fail mid-way MUST NOT leave the repository in a dirty state
- If a merge fails with conflicts, the merge MUST be aborted (not left pending)
- Working tree cleanliness is verified before operations

### REL-03: Graceful Degradation
- If Agent Mail is unreachable, audit entries MUST still be logged in-memory
- Audit entries queued in memory are flushed to Agent Mail when connectivity resumes
- Guard operations MUST NOT fail because of audit infrastructure being down

## Performance Requirements

### PERF-01: Validation Latency
- Path validation MUST complete in < 5ms
- Beads validation (issue existence check) MUST complete in < 500ms
- Git status checks MUST complete in < 2 seconds

### PERF-02: No Unnecessary I/O
- `validate_path()` should not hit disk -- only inspect the path string
- `validate_create()` should not call `bd` unless checking for cycles
