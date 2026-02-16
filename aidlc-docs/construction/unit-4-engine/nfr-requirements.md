<!-- beads-issue: gt-39 -->
<!-- beads-review: gt-40 -->
# NFR Requirements -- Unit 4: Context Dispatch + Agent Engine

## Reliability

### REL-01: Crash Recovery
- If the orchestrator process crashes, it MUST be able to reconstruct state from Beads + Agent Mail on restart
- `bd ready --json` and `bd list --status in_progress --json` provide current workflow state
- Agent Mail inbox shows pending messages and incomplete handshakes
- No in-memory-only critical state -- everything must be recoverable

### REL-02: Agent Timeout
- Each agent instance has a maximum lifetime (default: 1 hour)
- If an agent exceeds its timeout, the engine MUST stop it and log the timeout
- The stage issue should be updated to reflect the timeout failure
- Curious George should be notified to investigate

### REL-03: Graceful Shutdown
- `AgentEngine.shutdown()` MUST complete all in-progress agents or save their state
- Active dispatch messages must complete or be returned to the queue
- No orphaned agent instances after shutdown

### REL-04: Idempotent Dispatch
- If a dispatch message is sent twice (e.g., after crash recovery), the receiving agent must detect the duplicate and not create duplicate artifacts
- Detection: check if the Beads issue is already `done` or `in_progress`

## Concurrency

### CON-01: Agent Concurrency Limit
- Maximum concurrent agents is configurable (default: 4)
- Engine must queue excess dispatch requests and process them as agents complete
- No unbounded agent spawning

### CON-02: Project Isolation
- Agents from different projects must not interfere with each other
- Each project has its own Project Minder instance
- File reservations (via Agent Mail) prevent cross-project artifact conflicts

## State Persistence

### STATE-01: Project Registry Durability
- Project registry state must survive process restarts
- Stored in `{workspace}/.gorilla-troop/projects.json`
- Written atomically (write-to-temp-then-rename)

### STATE-02: Notification Persistence
- Unread notifications must survive restarts
- Stored alongside project registry
- On restart, Groomer reconstructs any notifications from Beads state changes

## Performance

### PERF-01: Dispatch Latency
- Building and sending a dispatch message: < 500ms
- Includes Agent Mail send + Beads issue update

### PERF-02: Engine Startup
- Engine initialization (load registry, connect to Agent Mail): < 5 seconds
- Does not include agent spawning time
