<!-- beads-issue: gt-49 -->
<!-- beads-review: gt-50 -->
# NFR Requirements -- Unit 5: Agent Definitions

## Security

### SEC-01: Agent Isolation
- Each agent instance runs with its own identity and can only access resources assigned to it
- Agents cannot impersonate other agents in Agent Mail (identity bound at registration)
- File reservations enforce editing boundaries between concurrent agents

### SEC-02: Prompt Injection Defense
- System prompts are loaded from versioned `.md` files, not constructed dynamically from user input
- All user/human input is wrapped in clear delimiters before being passed to agents
- Agents must not execute instructions embedded in artifact content -- only instructions from their system prompt and dispatch messages

### SEC-03: Snake Scanning Pipeline
- Snake MUST scan all code artifacts after Code Generation stage
- Snake MUST scan dependency manifests for known vulnerabilities
- Snake MUST detect hardcoded secrets (API keys, tokens, passwords)
- Scan results are persisted as artifacts and linked to Beads issues
- Critical findings block the Build & Test stage until resolved

### SEC-04: Tool Permission Boundaries
- Chimps can only use tools listed in their role definition
- Only Bonobo has write access to the filesystem and Git
- Only BeadsGuard-wrapped functions can modify Beads state
- Harmbe cannot execute code -- only route decisions

## Reliability

### REL-01: Agent Retry
- If an agent fails with a transient error (timeout, API error), retry up to 3 times with exponential backoff
- If all retries fail, report to Curious George

### REL-02: Error Escalation Chain
- Agent error -> Curious George investigates -> attempts fix -> if unfixable -> escalates to Harmbe -> human notified
- Maximum escalation depth: 2 (original agent -> Curious George -> Harmbe)

### REL-03: Rework Flow
- When a review gate is rejected, Gibbon receives the original artifact + feedback
- Gibbon has a maximum of 3 rework attempts before escalating to Harmbe
- Each rework attempt is logged in Beads with iteration count

### REL-04: Graceful Degradation
- If Agent Mail is unreachable, agents log messages locally and retry when connectivity resumes
- If Beads CLI fails, agents report the error but do not crash
- If the LLM API returns an error, agents retry with backoff

## Performance

### PERF-01: Agent Startup
- Agent initialization (load prompt, bind tools, register with Agent Mail): < 3 seconds
- Does not include LLM warmup time (first inference call)

### PERF-02: Context Window Management
- Input artifacts are loaded in priority order; if total exceeds context limits, lower-priority artifacts are summarized
- System prompts are kept under 4000 tokens
- Dispatch messages are kept under 2000 tokens
