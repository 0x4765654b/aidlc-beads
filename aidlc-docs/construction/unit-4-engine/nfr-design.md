<!-- beads-issue: gt-41 -->
<!-- beads-review: gt-42 -->
# NFR Design -- Unit 4: Context Dispatch + Agent Engine

## Pattern: Async Event Loop

The AgentEngine uses Python `asyncio` for concurrent agent management:
- `spawn_agent()` creates a new `asyncio.Task` for each agent
- A `Semaphore(max_concurrent_agents)` limits concurrency
- `shutdown()` calls `asyncio.gather()` on all active tasks with a timeout

```python
class AgentEngine:
    def __init__(self, config):
        self._semaphore = asyncio.Semaphore(config.max_concurrent_agents)
        self._tasks: dict[str, asyncio.Task] = {}
    
    async def spawn_agent(self, agent_type, context):
        await self._semaphore.acquire()
        task = asyncio.create_task(self._run_agent(agent_type, context))
        self._tasks[agent_id] = task
    
    async def _run_agent(self, agent_type, context):
        try:
            # Execute agent work
            ...
        finally:
            self._semaphore.release()
```

## Pattern: State Recovery

On startup, the engine reconstructs state from external stores:

1. Load `projects.json` for project registry
2. Query `bd list --status in_progress --json` for active stages
3. Query Agent Mail inbox for pending dispatch/completion messages
4. For each in-progress stage without an active agent, re-dispatch

This ensures REL-01 (crash recovery) without maintaining fragile in-memory checkpoints.

## Pattern: Graceful Shutdown

```
SIGTERM/SIGINT received
  -> Set shutdown flag
  -> Stop accepting new dispatches
  -> Wait up to 30s for active agents to complete
  -> Force-stop any remaining agents
  -> Save project registry to disk
  -> Close Agent Mail connections
  -> Exit
```

## Pattern: Notification Priority Queue

Use `heapq` for O(log n) insertion and O(log n) extraction:
- Priority key: `(priority, -created_at_timestamp)` so same-priority items are FIFO
- Thread-safe via `asyncio.Lock` (not threading.Lock -- we're async)

## Pattern: Atomic File Persistence

Project registry and notification state use write-to-temp-then-rename:

```python
async def _save_state(self, data: dict, path: Path):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(path)  # Atomic on POSIX, nearly atomic on Windows
```
