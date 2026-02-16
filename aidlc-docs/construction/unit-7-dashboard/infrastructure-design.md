<!-- beads-issue: gt-71 -->
<!-- beads-review: gt-72 -->
# Unit 7: Harmbe Dashboard -- Infrastructure Design

## Overview

The dashboard is a static React SPA served by a lightweight web server. In development, Vite provides hot-module replacement. In production, the built static assets are served by the Orchestrator API (FastAPI) or a dedicated nginx container.

---

## Development Setup

### Vite Dev Server

```bash
cd dashboard
npm install
npm run dev
# Starts on http://localhost:5173
# Proxies /api/* and /ws to http://localhost:8000 (Orchestrator API)
```

**Vite config proxy**:
```typescript
// vite.config.ts
export default defineConfig({
    server: {
        port: 5173,
        proxy: {
            "/api": "http://localhost:8000",
            "/ws": {
                target: "ws://localhost:8000",
                ws: true,
            },
        },
    },
});
```

This enables same-origin requests during development without CORS issues.

### Orchestrator API (Backend)

```bash
cd orchestrator
uvicorn orchestrator.api.app:create_app --factory --reload --port 8000
```

Both servers run concurrently during development.

---

## Production Build

### Build Command

```bash
cd dashboard
npm run build
# Output: dashboard/dist/
```

Produces optimized static assets (HTML, JS, CSS) in `dashboard/dist/`.

### Serving Strategy

**Option A (recommended for local)**: FastAPI serves the built assets as static files.

Add to `orchestrator/api/app.py`:
```python
from fastapi.staticfiles import StaticFiles
app.mount("/", StaticFiles(directory="dashboard/dist", html=True), name="dashboard")
```

This way, a single process (`uvicorn`) serves both the API and the dashboard.

**Option B (Docker production)**: Nginx serves static assets; API is a separate container. See Docker section below.

---

## Docker Configuration

### Dashboard Dockerfile

```dockerfile
# dashboard/Dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

### Nginx Config

```nginx
# dashboard/nginx.conf
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    # SPA fallback: all non-file routes serve index.html
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Proxy API requests to orchestrator
    location /api/ {
        proxy_pass http://orchestrator:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Proxy WebSocket
    location /ws {
        proxy_pass http://orchestrator:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

### Docker Compose Integration

The dashboard service will be added to the project-level `docker-compose.yml` in Unit 9:

```yaml
services:
  dashboard:
    build: ./dashboard
    ports:
      - "3000:80"
    depends_on:
      - orchestrator
```

---

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `VITE_API_URL` | `""` (same origin) | API base URL for production overrides |
| `VITE_WS_URL` | `""` (derived from window.location) | WebSocket URL override |

In development, the Vite proxy handles routing, so these are typically empty. In Docker, the nginx proxy handles it. These only need values if the dashboard is deployed separately from the API.

---

## Asset Pipeline

| Concern | Tool |
|---------|------|
| Bundler | Vite (esbuild for dev, Rollup for prod) |
| CSS | TailwindCSS (JIT, purged in production) |
| TypeScript | tsc (type checking), esbuild (transpilation) |
| Markdown rendering | react-markdown + rehype plugins |
| Code highlighting | rehype-highlight |

Production bundle targets: ES2020+ (modern browsers only for initial release).
