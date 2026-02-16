<!-- beads-issue: gt-59 -->
<!-- beads-review: gt-60 -->
# Unit 6: Orchestrator API -- NFR Requirements

## 1. Performance

### 1.1 API Response Time

| Endpoint Category | Target (p95) | Rationale |
|-------------------|-------------|-----------|
| Health / Info | < 50ms | Monitoring probes, no I/O |
| Project CRUD (registry) | < 200ms | In-memory registry + disk write |
| Notification list/count | < 100ms | In-memory priority queue |
| Review gate list | < 500ms | Requires Beads CLI subprocess |
| Question list | < 500ms | Requires Beads CLI subprocess |
| Chat (Harmbe dispatch) | < 30s | LLM inference; streaming preferred |
| Review approve/reject | < 1s | Beads update + Agent Mail send |
| Question answer | < 1s | Beads close + unblock check |

**NFR-PERF-01**: REST endpoints that do not invoke Beads CLI or LLM calls SHALL respond in under 200ms (p95).

**NFR-PERF-02**: REST endpoints that invoke Beads CLI SHALL respond in under 500ms (p95), excluding network latency to the client.

**NFR-PERF-03**: Chat responses MAY take up to 30 seconds for initial LLM response. If streaming is available, the first token SHOULD arrive within 3 seconds.

### 1.2 WebSocket Latency

**NFR-PERF-04**: WebSocket events SHALL be delivered to connected clients within 100ms of the triggering internal event.

**NFR-PERF-05**: WebSocket connection handshake SHALL complete within 500ms.

**NFR-PERF-06**: The server SHALL support at least 50 concurrent WebSocket connections without degradation.

### 1.3 Throughput

**NFR-PERF-07**: The API SHALL handle at least 100 REST requests per second under typical load (mix of project queries and notification reads).

**NFR-PERF-08**: WebSocket broadcast to all connected clients SHALL complete within 200ms regardless of client count (up to 50).

---

## 2. Reliability

### 2.1 Graceful Degradation

**NFR-REL-01**: If the Beads CLI is unavailable (e.g., subprocess failure), endpoints that depend on Beads SHALL return HTTP 503 (Service Unavailable) with a descriptive error message. Other endpoints SHALL continue functioning.

**NFR-REL-02**: If the Agent Mail server is unreachable, chat and review endpoints SHALL return HTTP 503 for Agent Mail-dependent operations but the API SHALL remain available for read-only operations (project list, notifications, health).

**NFR-REL-03**: If a WebSocket client disconnects unexpectedly, the server SHALL clean up the connection within 5 seconds without affecting other clients.

### 2.2 Error Isolation

**NFR-REL-04**: An unhandled exception in any single request handler SHALL NOT crash the server or affect other concurrent requests.

**NFR-REL-05**: WebSocket broadcast failures to individual clients SHALL be logged and the dead connection removed, but SHALL NOT prevent delivery to other clients.

### 2.3 Startup and Shutdown

**NFR-REL-06**: The FastAPI application SHALL start and be ready to serve requests within 5 seconds (excluding external dependency health checks).

**NFR-REL-07**: On shutdown (SIGTERM/SIGINT), the server SHALL:
1. Stop accepting new requests.
2. Close all WebSocket connections with a `1001 Going Away` close frame.
3. Shut down the AgentEngine gracefully (wait up to 30s for running agents).
4. Exit cleanly within 35 seconds.

---

## 3. Security

### 3.1 CORS

**NFR-SEC-01**: CORS SHALL be configured to allow only trusted origins. Default development configuration allows `localhost:3000` (dashboard dev server) and `localhost:8000` (self).

**NFR-SEC-02**: CORS configuration SHALL be overridable via environment variables (`ALLOWED_ORIGINS`).

### 3.2 Input Validation

**NFR-SEC-03**: All request bodies SHALL be validated by Pydantic models. Invalid input SHALL result in HTTP 422 with field-level error details.

**NFR-SEC-04**: Path parameters (project keys, issue IDs) SHALL be validated against expected patterns (alphanumeric + hyphens, max 64 chars) to prevent injection.

**NFR-SEC-05**: The `workspace_path` field in `CreateProjectRequest` SHALL be validated to ensure it is an existing directory. Path traversal sequences (`..`) SHALL be rejected.

### 3.3 Rate Limiting (Future)

**NFR-SEC-06**: The API SHOULD support optional rate limiting per client IP for production deployments. For initial local deployment, rate limiting is not required.

### 3.4 Authentication (Future)

**NFR-SEC-07**: For initial local-only deployment, authentication is deferred. The API design SHALL NOT preclude adding authentication middleware later (Bearer tokens or API keys).

---

## 4. Observability

### 4.1 Logging

**NFR-OBS-01**: All API requests SHALL be logged with: method, path, response status, duration (ms).

**NFR-OBS-02**: WebSocket connect/disconnect events SHALL be logged with client info and subscription filter.

**NFR-OBS-03**: Errors SHALL be logged with full stack traces at ERROR level.

### 4.2 Structured Events

**NFR-OBS-04**: The `/api/info` endpoint SHALL provide a real-time snapshot of system state: active projects, active agents, pending notifications, engine status.

---

## 5. Compatibility

**NFR-COMPAT-01**: The API SHALL use JSON for all request and response bodies.

**NFR-COMPAT-02**: The WebSocket protocol SHALL use JSON-formatted text frames (not binary).

**NFR-COMPAT-03**: The API SHALL serve on `0.0.0.0:8000` by default, configurable via `HOST` and `PORT` environment variables.

**NFR-COMPAT-04**: All datetime values in API responses SHALL use ISO 8601 format in UTC.
