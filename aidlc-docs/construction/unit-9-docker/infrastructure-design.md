<!-- beads-issue: gt-87 -->
<!-- beads-review: gt-88 -->
# Unit 9: Docker Infrastructure -- Infrastructure Design

## Service Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                     Host Machine (Developer Laptop)            │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                   Docker Compose                         │  │
│  │                                                          │  │
│  │  ┌──────────┐  ┌────────────┐  ┌──────────────────────┐ │  │
│  │  │Dashboard │  │Orchestrator│  │   Agent Mail Server  │ │  │
│  │  │ (nginx)  │  │ (FastAPI)  │  │   (Python HTTP)      │ │  │
│  │  │ :3000    │  │ :8000      │  │   :8080 (internal)   │ │  │
│  │  └──────────┘  └────────────┘  └──────────────────────┘ │  │
│  │                                                          │  │
│  │  ┌──────────┐  ┌────────────┐  ┌──────────────────────┐ │  │
│  │  │ Outline  │  │ PostgreSQL │  │   Redis              │ │  │
│  │  │ :3000int │  │ :5432 int  │  │   :6379 (internal)   │ │  │
│  │  └──────────┘  └────────────┘  └──────────────────────┘ │  │
│  │                                                          │  │
│  │  Network: gorilla-net (bridge)                           │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                │
│  Volumes: beads-data, agent-mail-data, outline-data,           │
│           postgres-data, redis-data                            │
│  Bind mounts: project workspace directories                   │
└────────────────────────────────────────────────────────────────┘
```

## Port Mapping

| Service | Internal Port | Host Port | Exposed? |
|---------|-------------|-----------|----------|
| dashboard | 80 | 3000 | Yes |
| orchestrator | 8000 | 8000 | Yes |
| agent-mail | 8080 | -- | No |
| outline | 3000 | -- | No (optional: 3001 for dev) |
| postgres | 5432 | -- | No |
| redis | 6379 | -- | No |

## Docker Compose Services

### 1. orchestrator
- **Image**: Custom Python 3.13 image
- **Build**: `Dockerfile.orchestrator`
- **Volumes**: Workspace bind mount, beads-data
- **Depends on**: agent-mail (healthy)
- **Environment**: AWS credentials, API config

### 2. dashboard
- **Image**: Custom nginx image (multi-stage build)
- **Build**: `Dockerfile.dashboard`
- **Depends on**: orchestrator (healthy)
- **Config**: nginx proxy to orchestrator for /api and /ws

### 3. agent-mail
- **Image**: `ghcr.io/dicklesworthstone/mcp_agent_mail:latest` or custom build
- **Volumes**: agent-mail-data
- **Health check**: HTTP /health

### 4. outline
- **Image**: `outlinewiki/outline:latest`
- **Volumes**: outline-data
- **Depends on**: postgres (healthy), redis (healthy)
- **Environment**: Database URL, Redis URL, secret key

### 5. postgres
- **Image**: `postgres:16-alpine`
- **Volumes**: postgres-data
- **Environment**: POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB

### 6. redis
- **Image**: `redis:7-alpine`
- **Volumes**: redis-data

## File Manifest

| File | Purpose |
|------|---------|
| `infra/docker-compose.yml` | Production compose file |
| `infra/docker-compose.dev.yml` | Development overrides |
| `infra/Dockerfile.orchestrator` | Orchestrator Python image |
| `infra/Dockerfile.dashboard` | Dashboard nginx image |
| `infra/nginx.conf` | Nginx config for dashboard |
| `infra/.env.example` | Environment variable template |
