<!-- beads-issue: gt-83 -->
<!-- beads-review: gt-84 -->
# Unit 9: Docker Infrastructure -- NFR Requirements

## 1. Reliability

**NFR-REL-01**: All services SHALL define health checks. A service is considered healthy only when its health check passes.

**NFR-REL-02**: Services SHALL use `restart: unless-stopped` to auto-recover from crashes.

**NFR-REL-03**: The orchestrator service SHALL wait for Agent Mail to be healthy before starting (dependency ordering).

**NFR-REL-04**: Named Docker volumes SHALL be used for persistent data (Beads database, Agent Mail data, Outline database) to survive container restarts.

**NFR-REL-05**: The `docker compose down` command SHALL NOT delete named volumes by default. Only `docker compose down -v` removes volumes.

## 2. Networking

**NFR-NET-01**: All services SHALL communicate over a single Docker bridge network (`gorilla-net`).

**NFR-NET-02**: Only the dashboard (port 3000) and orchestrator API (port 8000) SHALL expose ports to the host.

**NFR-NET-03**: Internal services (Agent Mail, Outline, database) SHALL NOT expose ports to the host in production mode.

## 3. Security

**NFR-SEC-01**: Secrets (AWS credentials, API keys) SHALL be passed via environment variables or `.env` file, never baked into images.

**NFR-SEC-02**: The `.env` file SHALL be listed in `.gitignore`. An `.env.example` with placeholder values SHALL be provided.

**NFR-SEC-03**: Containers SHALL run as non-root users where the base image supports it.

## 4. Performance

**NFR-PERF-01**: Health check intervals SHALL be 10 seconds with a 30-second start period to allow slow initialization.

**NFR-PERF-02**: The dashboard Dockerfile SHALL use multi-stage builds to minimize final image size.

## 5. Developer Experience

**NFR-DX-01**: `docker compose up` SHALL start all services with a single command.

**NFR-DX-02**: Development mode SHALL mount source directories as volumes for hot-reload.

**NFR-DX-03**: A `docker compose -f docker-compose.yml -f docker-compose.dev.yml up` override SHALL be available for development.
