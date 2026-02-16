<!-- beads-issue: gt-69 -->
<!-- beads-review: gt-70 -->
# Unit 7: Harmbe Dashboard -- NFR Design

## Overview

This document describes the design patterns and technical strategies used to satisfy the NFR requirements for the Harmbe Dashboard.

---

## Pattern 1: WebSocket Reconnection with Exponential Backoff

**Satisfies**: NFR-PERF-03, NFR-REL-01, NFR-REL-02

### Strategy

The `useWebSocket` hook manages a persistent WebSocket connection with automatic reconnection:

```
Initial connect
    │
    ▼
Connected ──[message]──▶ dispatch to subscribers
    │
    │ (connection lost)
    ▼
Disconnected ──▶ wait(delay) ──▶ reconnect attempt
    │                               │
    │ (success)                     │ (fail)
    ▼                               ▼
Connected                    wait(delay * 2, max 30s)
                                    │
                                    ▼
                             reconnect attempt ──▶ ...
```

### Implementation

```typescript
const INITIAL_DELAY = 1000;   // 1 second
const MAX_DELAY = 30000;      // 30 seconds
const BACKOFF_FACTOR = 2;

// On disconnect:
// 1. Set isConnected = false
// 2. Show "Offline - reconnecting..." banner
// 3. Start reconnection loop with exponential backoff
// On reconnect:
// 1. Set isConnected = true
// 2. Hide offline banner
// 3. Fetch latest state from REST endpoints to resync
//    (notifications count, project list, review gates)
```

### Resync on Reconnect

After a successful reconnect, the hook emits a `reconnected` event. Components listening for this event re-fetch their data from REST to catch any events missed during the disconnection.

---

## Pattern 2: Optimistic UI for Chat Messages

**Satisfies**: NFR-PERF-04, NFR-UX-04

### Strategy

When the user sends a chat message:

1. **Immediately** append the user's message to the local message list with `status: "sent"`.
2. Show a typing indicator below the user's message.
3. Fire the `POST /api/chat/` request.
4. On success: append the assistant response, remove typing indicator.
5. On failure: mark the user's message with `status: "failed"`, show retry button.

### State Model

```typescript
interface LocalMessage {
    id: string;          // Client-generated UUID
    role: "user" | "assistant";
    content: string;
    status: "sent" | "delivered" | "failed";
    timestamp: string;
}
```

Messages are stored in React state (`useState<LocalMessage[]>`), scoped per project key. Switching projects swaps the message array (cached in a `Map<string, LocalMessage[]>`).

---

## Pattern 3: Subscription-Based Event Dispatch

**Satisfies**: NFR-PERF-04 (WebSocket latency), NFR-REL-02

### Strategy

Rather than passing WebSocket events through a global store, the `useWebSocket` hook uses a **publish-subscribe** pattern:

```typescript
// In the hook:
const subscribers = useRef<Map<string, Set<(data: any) => void>>>();

function subscribe(eventType: string, handler: (data: any) => void) {
    // Add handler to the set for this eventType
    // Return unsubscribe function
}

// On incoming WebSocket message:
function onMessage(event: MessageEvent) {
    const { event: eventType, data } = JSON.parse(event.data);
    const handlers = subscribers.current.get(eventType);
    handlers?.forEach(h => h(data));
}
```

### Component Usage

Each component subscribes to only the events it cares about:

```typescript
// In ReviewPanel:
useEffect(() => {
    const unsub = subscribe("review_ready", (data) => {
        setReviews(prev => [...prev, data]);
    });
    return unsub;
}, [subscribe]);
```

This keeps re-renders localized -- a `stage_completed` event only triggers updates in `StatusPanel`, not in `ChatPanel`.

---

## Pattern 4: Feature-Based Component Organization

**Satisfies**: NFR-MAINT-01, NFR-MAINT-02

### Directory Structure

```
dashboard/src/
├── components/
│   ├── layout/        # Sidebar, NavBar, NewProjectDialog
│   ├── chat/          # ChatPanel, MessageList, MessageBubble, ChatInput
│   ├── review/        # ReviewPanel, ReviewList, ReviewDetail, ReviewActions
│   ├── status/        # StatusPanel, AgentTable
│   ├── notifications/ # NotificationsPanel, NotificationItem
│   └── questions/     # QuestionsPanel, QuestionDetail, AnswerForm
├── context/           # AppContext (active project, unread count)
├── hooks/             # useWebSocket, useApi (optional wrapper)
├── services/          # api.ts (REST client)
├── types/             # Shared TypeScript types matching API models
├── App.tsx            # Root layout + React Router
└── main.tsx           # Entry point
```

### Type Sharing

All API response types are defined once in `types/api.ts`, matching the Pydantic models from Unit 6:

```typescript
// types/api.ts
export interface ProjectResponse { ... }
export interface ChatResponse { ... }
export interface ReviewGateResponse { ... }
export interface NotificationResponse { ... }
// etc.
```

Components import from this single file, ensuring consistency with the backend.

---

## Pattern 5: Loading and Error State Machine

**Satisfies**: NFR-UX-04, NFR-UX-05, NFR-REL-01

### Strategy

Every data-fetching component follows a 3-state model:

```typescript
type FetchState<T> =
    | { status: "loading" }
    | { status: "success"; data: T }
    | { status: "error"; error: string; retry: () => void };
```

### Rendering Rules

- `loading`: Show skeleton UI or spinner (within 200ms).
- `success`: Render data.
- `error`: Show error message + retry button. Never show raw exceptions.

### Implementation

A helper hook `useFetch<T>(fetcher)` encapsulates this pattern:

```typescript
function useFetch<T>(fetcher: () => Promise<T>): FetchState<T> {
    const [state, setState] = useState<FetchState<T>>({ status: "loading" });

    const execute = useCallback(async () => {
        setState({ status: "loading" });
        try {
            const data = await fetcher();
            setState({ status: "success", data });
        } catch (e) {
            setState({
                status: "error",
                error: e instanceof Error ? e.message : "Unknown error",
                retry: execute,
            });
        }
    }, [fetcher]);

    useEffect(() => { execute(); }, [execute]);
    return state;
}
```

---

## Pattern 6: Markdown Rendering with Sanitization

**Satisfies**: NFR-UX-08, NFR-SEC-02

### Strategy

Artifact content (review documents) is rendered using `react-markdown` with:

- **Syntax highlighting**: `rehype-highlight` for code blocks.
- **Sanitization**: `rehype-sanitize` to strip dangerous HTML.
- **Tables**: GitHub-flavored Markdown (GFM) plugin for table support.

```typescript
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import rehypeSanitize from "rehype-sanitize";

<ReactMarkdown
    remarkPlugins={[remarkGfm]}
    rehypePlugins={[rehypeHighlight, rehypeSanitize]}
>
    {artifactContent}
</ReactMarkdown>
```

User-provided text in chat messages uses the same pipeline, preventing XSS from injected content.

---

## Pattern 7: Debounced Notification Badge

**Satisfies**: NFR-UX-07, NFR-PERF-05

### Strategy

The notification badge count is maintained in `AppContext` and updated by:

1. **Initial load**: `GET /api/notifications/count` on app mount.
2. **WebSocket events**: Increment on `notification_new`, decrement on `notification_read`.
3. **Debounce**: Multiple rapid events (e.g., batch stage completions) are debounced to avoid flickering. The count updates at most once per 500ms.

This avoids re-fetching the count on every event while keeping the badge accurate.
