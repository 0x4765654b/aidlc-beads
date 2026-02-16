<!-- beads-issue: gt-51 -->
<!-- beads-review: gt-52 -->
# NFR Design -- Unit 5: Agent Definitions

## Pattern: Agent Retry with Exponential Backoff

```python
MAX_RETRIES = 3
BASE_DELAY = 2.0  # seconds

async def with_retry(func, *args, **kwargs):
    for attempt in range(MAX_RETRIES):
        try:
            return await func(*args, **kwargs)
        except (TimeoutError, ConnectionError) as e:
            if attempt == MAX_RETRIES - 1:
                raise
            delay = BASE_DELAY * (2 ** attempt)
            logger.warning("Retry %d/%d after %.1fs: %s", attempt + 1, MAX_RETRIES, delay, e)
            await asyncio.sleep(delay)
```

Applied in `BaseAgent.handle_dispatch()` -- wraps the entire `_execute()` call.

## Pattern: Error Escalation Chain

```
BaseAgent._execute() raises Exception
  -> BaseAgent.handle_dispatch() catches it
  -> Sends error report to CuriousGeorge via Agent Mail
  -> CuriousGeorge.investigate()
     -> If fixable: applies fix via Bonobo, returns success
     -> If unfixable: sends diagnostic to Harmbe
  -> Harmbe queues notification for human
```

Each step is an Agent Mail message in the thread `{issue_id}-error`:
- Original error: `[ERROR] {agent_type}: {error_summary}`
- Investigation: `[INVESTIGATING] CuriousGeorge: {analysis}`
- Resolution: `[RESOLVED] CuriousGeorge: {fix_description}` OR `[ESCALATED] CuriousGeorge: {diagnostic}`

## Pattern: Rework Chain with Iteration Tracking

```python
class GibbonReworkTracker:
    MAX_REWORK_ITERATIONS = 3
    
    async def handle_rework(self, issue_id, feedback, iteration=1):
        if iteration > self.MAX_REWORK_ITERATIONS:
            await self.escalate_to_harmbe(issue_id, "Max rework attempts exceeded")
            return
        
        # Load original artifact + feedback
        # Apply corrections
        # Resubmit for review
        # If rejected again, recursion with iteration + 1
```

Beads issue notes track iteration: `rework-iteration: N`

## Pattern: Tool Permission Registry

```python
AGENT_TOOL_REGISTRY = {
    "Scout": ["read_file", "list_directory", "search_code", "scribe_create_artifact", "scribe_validate"],
    "Sage": ["read_artifact", "scribe_create_artifact", "scribe_update_artifact"],
    "Forge": ["read_artifact", "read_file", "write_code_file", "git_commit", "run_linter"],
    # ... all roles
}

class ToolGuard:
    def validate_tool_access(self, agent_type: str, tool_name: str) -> bool:
        allowed = AGENT_TOOL_REGISTRY.get(agent_type, [])
        return tool_name in allowed
```

Enforced in `BaseAgent._get_tools()` -- only returns tools the agent is authorized to use.

## Pattern: Context Window Budgeting

```python
MAX_CONTEXT_TOKENS = 180_000  # ~90% of 200K limit for Opus
SYSTEM_PROMPT_BUDGET = 4_000
DISPATCH_BUDGET = 2_000
ARTIFACT_BUDGET = MAX_CONTEXT_TOKENS - SYSTEM_PROMPT_BUDGET - DISPATCH_BUDGET

async def load_context(artifacts: list[str], budget: int = ARTIFACT_BUDGET) -> str:
    """Load artifacts, fitting within token budget.
    
    Priority: input_artifacts first, then reference_docs.
    If over budget, truncate lowest-priority artifacts with a summary note.
    """
```
