<!-- beads-issue: gt-7 -->
<!-- beads-review: gt-12 -->
# Execution Plan -- Gorilla Troop

## Analysis Summary

### Change Impact Assessment

- **User-facing changes**: Yes -- entirely new system with dashboard, CLI, and enhanced Outline
- **Structural changes**: Yes -- new orchestrator process, agent modules, Docker services, communication layer
- **Data model changes**: Minimal -- reuses existing Beads schema, adds Agent Mail schema and project registry
- **API changes**: Yes -- new dashboard REST/WebSocket API, gt CLI, enhanced sync-outline.py
- **NFR impact**: Yes -- security (credential management, code scanning), reliability (crash recovery, state persistence), observability (structured logging)

### Risk Assessment

- **Risk Level**: Medium-High
  - Multiple integration points (Strands Agents, Bedrock, Agent Mail, Beads, Outline, Docker)
  - Agent behavior is non-deterministic (LLM-based); extensive testing of agent prompts required
  - Docker bind mount filesystem model has platform-specific behavior (Windows vs Linux paths)
- **Rollback Complexity**: Easy -- Gorilla Troop is additive. The existing AIDLC-Beads framework is untouched. Removing Gorilla Troop requires only deleting the gorilla-troop directory.

### Mitigation Strategies

1. Build incrementally per the Implementation Phases in the architecture doc
2. Test each agent in isolation before integration
3. Use Beads issue tracking to manage discovered work
4. Docker Compose enables rapid environment reset

---

## Stages to Execute

### INCEPTION PHASE

| Stage | Status | Rationale |
|-------|--------|-----------|
| Workspace Detection | COMPLETED (gt-4) | Brownfield detected |
| Reverse Engineering | COMPLETED (gt-15) | 8 artifacts documenting existing codebase |
| Requirements Analysis | COMPLETED (gt-5) | 13 FR groups, 8 NFR groups |
| User Stories | COMPLETED (gt-6) | 3 personas, 16 stories |
| Workflow Planning | IN PROGRESS (gt-7) | This document |
| Application Design | **EXECUTE** (gt-8) | Complex multi-component system. Need detailed component specs, service interfaces, and dependency mapping beyond the high-level architecture doc. |
| Units Generation | **EXECUTE** (gt-9) | System decomposes into 6+ distinct units. Each needs its own Construction cycle with design, code, and testing. |

### CONSTRUCTION PHASE (Per Unit)

All Construction stages will **EXECUTE** for this project:

| Stage | Decision | Rationale |
|-------|----------|-----------|
| Functional Design | **EXECUTE** | Complex business logic: agent orchestration, Context Dispatch Protocol, review workflows, merge intelligence, error recovery chains |
| NFR Requirements | **EXECUTE** | Security (credential management, code scanning), reliability (crash recovery), observability (structured logging) -- all identified as requirements |
| NFR Design | **EXECUTE** | Need design patterns: resilience (Beads state persistence, Agent Mail durability), security (Bonobo write guards, Snake scanning pipeline), observability (log format, audit trails) |
| Infrastructure Design | **EXECUTE** | Docker Compose with 6 services, volume mounts, networking, AWS migration path documented in architecture. Need IaC artifacts. |
| Code Generation | **EXECUTE** (always) | Core implementation |
| Build and Test | **EXECUTE** (always) | Validation |

**Stages Skipped: NONE** -- all stages execute due to system complexity.

### OPERATIONS PHASE

Operations is deferred until Construction is complete. Will include Docker Compose finalization and documentation for AWS migration.

---

## Unit Decomposition Preview

Based on the architecture document's Implementation Phases, the system decomposes into these approximate units (to be finalized in Units Generation):

| Unit | Description | Key Components |
|------|-------------|----------------|
| **scribe-library** | Artifact management tool library | Python module, create/validate/register functions |
| **agent-core** | Agent definitions and system prompts | Strands agent configs for all 16 roles |
| **orchestrator** | Main orchestrator process | Harmbe, Project Minder, Groomer event loops, agent spawning |
| **bonobo-guards** | Privileged operation wrappers | File Bonobo, Git Bonobo, Beads Bonobo |
| **dashboard** | Harmbe Dashboard web app | FastAPI backend, React frontend, WebSocket |
| **gt-cli** | Command-line interface | Thin CLI wrapper for Harmbe commands |
| **agent-mail-integration** | Agent Mail setup and conventions | Docker config, identity registration, thread conventions |
| **outline-enhanced** | Enhanced Outline integration | Status flags, action buttons, enhanced sync-outline.py |
| **docker-infra** | Docker Compose and configuration | docker-compose.yml, .env, networking, volumes |

---

## Beads Dependency Chain

### Current Active Chain

```
gt-4  (Workspace Detection)     [DONE]
  └── gt-15 (Reverse Engineering) [DONE]
      └── gt-10 (REVIEW: RE)      [DONE]
          └── gt-5  (Requirements) [DONE]
              └── gt-16 (REVIEW: Req) [DONE]
                  └── gt-6  (User Stories) [DONE]
                      └── gt-11 (REVIEW: US) [DONE]
                          └── gt-7  (Workflow Planning) [IN PROGRESS]
                              └── gt-12 (REVIEW: WP) [PENDING]
                                  └── gt-8  (Application Design) [PENDING]
                                      └── gt-13 (REVIEW: AD) [PENDING]
                                          └── gt-9  (Units Generation) [PENDING]
                                              └── gt-14 (REVIEW: UG) [PENDING]
                                                  └── Construction begins
```

### Construction Chain (to be wired during Units Generation)

For each unit, the Construction chain will be:

```
Functional Design → [REVIEW] → NFR Requirements → [REVIEW] → NFR Design → [REVIEW]
→ Infrastructure Design → [REVIEW] → Code Generation → Snake Review → [REVIEW]
→ Build and Test → [REVIEW]
```

---

## Estimated Timeline

- **Remaining Inception Stages**: 2 (Application Design, Units Generation)
- **Construction Units**: ~9 (see unit decomposition above)
- **Construction Stages Per Unit**: 6 (+ review gates)
- **Total Remaining Stages**: ~56 Construction stages + 2 Inception stages
- **Estimated Duration**: Dominated by LLM latency and human review time. Automated execution: days. With human review gates: weeks (depending on reviewer availability).

---

## Next Steps After Approval

1. **Application Design** (gt-8): Detail component specifications, service interfaces, Python module structure, and deployment mapping.
2. **Units Generation** (gt-9): Formalize the units above with precise boundaries, dependencies, and Construction stage plans for each.
3. **Construction**: Begin unit-by-unit design, implementation, and testing.
