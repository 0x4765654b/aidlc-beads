<!-- beads-issue: gt-85 -->
<!-- beads-review: gt-86 -->
# Unit 9: Docker Infrastructure -- NFR Design

## Pattern 1: Service Health Checks

Each service defines a health check command:

| Service | Health Check | Interval | Start Period |
|---------|-------------|----------|-------------|
| orchestrator | `curl -f http://localhost:8000/api/health` | 10s | 30s |
| dashboard | `curl -f http://localhost:80/` | 10s | 15s |
| agent-mail | `curl -f http://localhost:8080/health` | 10s | 30s |
| outline | `curl -f http://localhost:3000/api/info` | 10s | 45s |
| postgres | `pg_isready -U outline` | 10s | 15s |
| redis | `redis-cli ping` | 10s | 10s |

## Pattern 2: Network Isolation

```
gorilla-net (bridge)
├── orchestrator (8000 -> host)
├── dashboard (3000 -> host)
├── agent-mail (internal only)
├── outline (internal only)
├── postgres (internal only)
└── redis (internal only)
```

Only orchestrator and dashboard expose ports. All inter-service communication uses Docker DNS (service names as hostnames).

## Pattern 3: Volume Strategy

| Volume | Mount Path | Purpose |
|--------|-----------|---------|
| `beads-data` | `/workspace/.beads` | Beads database persistence |
| `agent-mail-data` | `/data` | Agent Mail message storage |
| `outline-data` | `/var/lib/outline/data` | Outline wiki data |
| `postgres-data` | `/var/lib/postgresql/data` | Outline database |
| `redis-data` | `/data` | Redis persistence |

Project workspaces are bind-mounted from the host for shared Git access.

## Pattern 4: Credential Mounting

AWS credentials for Bedrock access:

```yaml
environment:
  - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
  - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
  - AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION:-us-east-1}
```

Alternatively, mount `~/.aws/credentials` as a read-only volume:

```yaml
volumes:
  - ${HOME}/.aws:/home/app/.aws:ro
```

## Pattern 5: Multi-Stage Dockerfile (Dashboard)

```
Stage 1: node:20-alpine (build) -> npm ci, npm run build
Stage 2: nginx:alpine (runtime) -> copy dist/, nginx.conf only
```

Final image contains only static assets + nginx. No Node.js runtime, no node_modules.

## Pattern 6: Development Override

`docker-compose.dev.yml` adds:
- Source code volumes for hot-reload
- Exposed ports for internal services (debugging)
- `--reload` flag for uvicorn
- Vite dev server instead of nginx
