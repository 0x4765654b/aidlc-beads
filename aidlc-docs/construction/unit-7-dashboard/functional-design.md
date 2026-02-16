<!-- beads-issue: gt-65 -->
<!-- beads-review: gt-66 -->
# Unit 7: Harmbe Dashboard -- Functional Design

## Overview

The Harmbe Dashboard is a **React single-page application** that serves as the primary human interface to the Gorilla Troop system. It communicates with the Orchestrator API (Unit 6) over REST and WebSocket, providing real-time visibility into project state and enabling human decisions (review approvals, Q&A answers, chat).

**Technology stack**: React 18+, TypeScript, Vite (build), TailwindCSS (styling), React Router (navigation).

---

## Layout Architecture

The dashboard uses a responsive **sidebar + main content** layout:

```
┌──────────┬──────────────────────────────────────────────┐
│          │  Notification Bar          [🔔 3]  [ℹ️ Info] │
│ Project  ├──────────────────────────────────────────────┤
│ Sidebar  │                                              │
│          │              Main Content Area               │
│ ● Proj A │                                              │
│ ○ Proj B │   (Chat | Review | Status | Notifications)   │
│ ◉ Proj C │                                              │
│          │                                              │
│ [+ New]  │                                              │
│          │                                              │
└──────────┴──────────────────────────────────────────────┘
```

### Regions

| Region | Width | Purpose |
|--------|-------|---------|
| **Project Sidebar** | 240px (collapsible) | Project list with status indicators, new project button |
| **Notification Bar** | Full width, 48px | Unread count badge, system info toggle |
| **Main Content** | Remaining | Active panel content, switches based on navigation |

---

## Panels (Pages)

### 1. Chat Panel (`/chat`)

**Purpose**: Real-time conversational interface with Harmbe.

**Layout**:
```
┌────────────────────────────────────────┐
│ Chat with Harmbe          [Project: X] │
├────────────────────────────────────────┤
│                                        │
│  [User] What's the project status?     │
│                                        │
│  [Harmbe] Project X is in Construction │
│  phase. Unit 3 is in progress...       │
│                                        │
│  [User] Approve the requirements doc   │
│                                        │
│  [Harmbe] ✓ Requirements approved.     │
│  Next stage dispatched: User Stories.  │
│                                        │
├────────────────────────────────────────┤
│ [Type a message...              ] [⏎]  │
└────────────────────────────────────────┘
```

**Components**:
- `ChatPanel` -- Container component
- `MessageList` -- Scrollable message history (auto-scroll to bottom)
- `MessageBubble` -- Individual message (user/assistant, markdown rendering)
- `ChatInput` -- Text input with send button, Enter-to-send

**API Interactions**:
- `POST /api/chat/` -- Send message, get Harmbe response
- `GET /api/chat/history?project_key=X` -- Load history on panel mount
- WebSocket `chat_message` events update the list in real-time

**Behavior**:
- Messages render markdown (code blocks, bold, lists).
- A typing indicator shows while waiting for Harmbe's response.
- Project context selector at the top filters chat to a specific project.
- Messages are scoped per project; switching projects loads different history.

---

### 2. Document Review Panel (`/review`)

**Purpose**: View and approve/reject AIDLC artifacts.

**Layout**:
```
┌────────────────────────────────────────┐
│ Pending Reviews (3)                    │
├────────────────────────────────────────┤
│ ▸ Requirements Analysis   [gt-12]  ●   │
│ ▸ Application Design      [gt-14]      │
│ ▸ Unit 3 Functional Design [gt-32]     │
├────────────────────────────────────────┤
│                                        │
│ # Requirements Analysis                │
│                                        │
│ (Rendered markdown content of the      │
│  artifact, loaded from API)            │
│                                        │
│                                        │
├────────────────────────────────────────┤
│ Feedback:                              │
│ [                                    ] │
│                                        │
│ [✓ Approve]  [✕ Request Changes]       │
└────────────────────────────────────────┘
```

**Components**:
- `ReviewPanel` -- Container with list + detail split
- `ReviewList` -- List of pending review gates (from API)
- `ReviewDetail` -- Markdown viewer with the artifact content
- `ReviewActions` -- Approve/reject buttons + feedback textarea

**API Interactions**:
- `GET /api/review/` -- List pending review gates
- `GET /api/review/{issue_id}` -- Load artifact content
- `POST /api/review/{issue_id}/approve` -- Approve with optional feedback
- `POST /api/review/{issue_id}/reject` -- Reject with feedback (required)
- WebSocket events: `review_ready`, `review_approved`, `review_rejected`

**Behavior**:
- Selecting a review gate loads and renders the artifact markdown.
- Approve sends the decision; the review disappears from the list.
- Reject requires feedback text; dispatches rework notification.
- Real-time: new review gates appear in the list via WebSocket.
- Badge count on the panel tab shows pending review count.

---

### 3. Project Status Panel (`/status`)

**Purpose**: Visual overview of the current project's AIDLC workflow.

**Layout**:
```
┌────────────────────────────────────────┐
│ Project: Gorilla Troop     [Active]    │
├────────────────────────────────────────┤
│ Phase: Construction                    │
│ Active Agents: 2 | Pending Reviews: 1  │
├────────────────────────────────────────┤
│                                        │
│ Ready Issues:                          │
│   • Unit 4: Code Generation  [gt-43]  │
│                                        │
│ In Progress:                           │
│   • Unit 3: Build and Test   [gt-35]  │
│     Agent: crucible-a1b2c3d4           │
│                                        │
│ Agents:                                │
│   ┌──────────┬────────┬──────────┐     │
│   │ Agent    │ Type   │ Task     │     │
│   ├──────────┼────────┼──────────┤     │
│   │ forge-x  │ Forge  │ gt-43    │     │
│   │ crucible │ Crucbl │ gt-35    │     │
│   └──────────┴────────┴──────────┘     │
│                                        │
└────────────────────────────────────────┘
```

**Components**:
- `StatusPanel` -- Container
- `ProjectHeader` -- Name, status badge, phase indicator
- `StatusSummary` -- Active agents count, pending reviews, open questions
- `IssueList` -- Ready and in-progress issues
- `AgentTable` -- Active agents for this project

**API Interactions**:
- `GET /api/projects/{key}/status` -- Project status summary
- `GET /api/projects/{key}/agents` -- Active agents
- WebSocket events: `stage_started`, `stage_completed`, `agent_spawned`, `agent_stopped`

**Behavior**:
- Auto-refreshes via WebSocket events (no polling).
- Status badges: green (active), yellow (paused), gray (completed).
- Clicking an issue ID could navigate to the review panel if it's a review gate.

---

### 4. Notifications Panel (`/notifications`)

**Purpose**: Centralized view of all human-attention items.

**Layout**:
```
┌────────────────────────────────────────┐
│ Notifications          [Mark All Read] │
├────────────────────────────────────────┤
│ ● [P0] Review gate ready: Req Analysis│
│   Project: gorilla-troop   2m ago      │
│                                        │
│ ● [P0] Error escalation: Forge timeout │
│   Project: my-app          15m ago     │
│                                        │
│ ○ [P2] Stage completed: User Stories   │
│   Project: gorilla-troop   1h ago      │
│                                        │
│ ○ [P3] Question answered: Auth method  │
│   Project: my-app          2h ago      │
│                                        │
└────────────────────────────────────────┘
```

**Components**:
- `NotificationsPanel` -- Container
- `NotificationItem` -- Single notification with priority badge, timestamp
- `NotificationFilters` -- Filter by project, type, read/unread

**API Interactions**:
- `GET /api/notifications/?project_key=X&limit=50` -- List notifications
- `GET /api/notifications/count` -- Unread count (for badge)
- `POST /api/notifications/{id}/read` -- Mark as read
- `POST /api/notifications/read-all` -- Mark all as read
- WebSocket: `notification_new` adds to the list in real-time

**Behavior**:
- Sorted by priority (P0 first), then by time.
- Unread notifications have a filled dot; read have an empty dot.
- Clicking a review gate notification navigates to the Review panel.
- Clicking a Q&A notification navigates to the Questions panel.
- Badge count in the notification bar updates in real-time.

---

### 5. Questions Panel (`/questions`)

**Purpose**: View and answer pending Q&A questions from agents.

**Layout**:
```
┌────────────────────────────────────────┐
│ Pending Questions (2)                  │
├────────────────────────────────────────┤
│ ▸ Authentication Method    [gt-25]     │
│ ▸ Database Strategy        [gt-31]     │
├────────────────────────────────────────┤
│                                        │
│ QUESTION: Requirements - Auth Method   │
│                                        │
│ Which authentication approach?         │
│                                        │
│   ○ A) OAuth/SSO                       │
│   ○ B) Username/Password               │
│   ○ C) API Keys                        │
│   ○ X) Other                           │
│                                        │
│ Custom answer: [                     ] │
│                                        │
│ [Submit Answer]                        │
└────────────────────────────────────────┘
```

**Components**:
- `QuestionsPanel` -- Container with list + detail split
- `QuestionList` -- Pending questions from API
- `QuestionDetail` -- Full question with parsed options
- `AnswerForm` -- Radio buttons for options + free-text for "Other"

**API Interactions**:
- `GET /api/questions/` -- List pending questions
- `GET /api/questions/{issue_id}` -- Question detail with options
- `POST /api/questions/{issue_id}/answer` -- Submit answer
- WebSocket: `question_asked`, `question_answered`

**Behavior**:
- Options are rendered as radio buttons; selecting "Other" reveals a text field.
- Submitting an answer closes the question and removes it from the list.
- Real-time: new questions appear via WebSocket.

---

## Project Sidebar

**Components**:
- `ProjectSidebar` -- Container
- `ProjectItem` -- Single project with status indicator
- `NewProjectDialog` -- Modal form for creating a project

**Status Indicators**:
| Color | Meaning |
|-------|---------|
| Green (●) | Active, progressing |
| Yellow (◉) | Waiting for human action (pending review/question) |
| Red (✕) | Error or escalation |
| Gray (○) | Paused or completed |

**API Interactions**:
- `GET /api/projects/` -- List all projects
- `POST /api/projects/` -- Create new project
- `POST /api/projects/{key}/pause` -- Pause
- `POST /api/projects/{key}/resume` -- Resume

**Behavior**:
- Clicking a project sets it as the active context for all panels.
- Right-click context menu: Pause, Resume, Delete.
- The `[+ New]` button opens the `NewProjectDialog` modal.
- Status indicators update in real-time via WebSocket project events.

---

## Shared Infrastructure

### API Client (`services/api.ts`)

A typed REST client wrapping `fetch`:

```typescript
// All methods return typed responses
api.projects.list(status?: string): Promise<ProjectResponse[]>
api.projects.get(key: string): Promise<ProjectResponse>
api.projects.create(body: CreateProjectRequest): Promise<ProjectResponse>
api.projects.pause(key: string): Promise<ProjectResponse>
api.projects.resume(key: string): Promise<ProjectResponse>
api.projects.delete(key: string): Promise<void>
api.projects.status(key: string): Promise<ProjectStatusResponse>
api.projects.agents(key: string): Promise<AgentResponse[]>

api.chat.send(message: string, projectKey?: string): Promise<ChatResponse>
api.chat.history(projectKey?: string, limit?: number): Promise<ChatMessage[]>

api.review.list(projectKey?: string): Promise<ReviewGateResponse[]>
api.review.get(issueId: string): Promise<ReviewDetailResponse>
api.review.approve(issueId: string, feedback?: string): Promise<ReviewResultResponse>
api.review.reject(issueId: string, feedback: string): Promise<ReviewResultResponse>

api.notifications.list(projectKey?: string, limit?: number): Promise<NotificationResponse[]>
api.notifications.count(projectKey?: string): Promise<NotificationCountResponse>
api.notifications.markRead(id: string): Promise<void>
api.notifications.markAllRead(projectKey?: string): Promise<{ marked: number }>

api.questions.list(projectKey?: string): Promise<QuestionResponse[]>
api.questions.get(issueId: string): Promise<QuestionDetailResponse>
api.questions.answer(issueId: string, answer: string): Promise<AnswerResultResponse>

api.health(): Promise<{ status: string }>
api.info(): Promise<SystemInfoResponse>
```

### WebSocket Hook (`hooks/useWebSocket.ts`)

```typescript
function useWebSocket(projectKey?: string): {
    lastEvent: WebSocketEvent | null;
    isConnected: boolean;
    subscribe: (eventType: string, handler: (data: any) => void) => () => void;
}
```

- Manages connection lifecycle (connect, reconnect with backoff, disconnect on unmount).
- Filters events by `projectKey`.
- `subscribe()` returns an unsubscribe function for cleanup.
- Exposes connection status for UI indicators.

### App State (React Context)

```typescript
interface AppState {
    activeProject: string | null;
    setActiveProject: (key: string | null) => void;
    unreadCount: number;
    setUnreadCount: (count: number) => void;
}
```

Stored in a `React.createContext` provider at the app root.

---

## Routing

| Path | Panel | Description |
|------|-------|-------------|
| `/` | Redirect to `/chat` | Default landing |
| `/chat` | Chat Panel | Conversation with Harmbe |
| `/review` | Review Panel | Pending review gates |
| `/review/:issueId` | Review Detail | Specific review with artifact |
| `/status` | Status Panel | Project workflow overview |
| `/notifications` | Notifications | All notifications |
| `/questions` | Questions Panel | Pending Q&A |
| `/questions/:issueId` | Question Detail | Specific question |

---

## File Manifest

| File | Purpose | Lines (est.) |
|------|---------|-------------|
| `dashboard/package.json` | Dependencies and scripts | ~30 |
| `dashboard/tsconfig.json` | TypeScript configuration | ~20 |
| `dashboard/vite.config.ts` | Vite build configuration | ~15 |
| `dashboard/tailwind.config.js` | TailwindCSS configuration | ~15 |
| `dashboard/index.html` | HTML entry point | ~15 |
| `dashboard/src/main.tsx` | React app entry point | ~15 |
| `dashboard/src/App.tsx` | Root layout + routing | ~60 |
| `dashboard/src/context/AppContext.tsx` | App-wide state context | ~40 |
| `dashboard/src/services/api.ts` | Typed REST client | ~150 |
| `dashboard/src/hooks/useWebSocket.ts` | WebSocket hook with reconnection | ~80 |
| `dashboard/src/components/layout/Sidebar.tsx` | Project sidebar | ~80 |
| `dashboard/src/components/layout/NavBar.tsx` | Top navigation + notification badge | ~50 |
| `dashboard/src/components/layout/NewProjectDialog.tsx` | Create project modal | ~70 |
| `dashboard/src/components/chat/ChatPanel.tsx` | Chat container | ~60 |
| `dashboard/src/components/chat/MessageList.tsx` | Message history display | ~50 |
| `dashboard/src/components/chat/MessageBubble.tsx` | Single message rendering | ~40 |
| `dashboard/src/components/chat/ChatInput.tsx` | Message input box | ~40 |
| `dashboard/src/components/review/ReviewPanel.tsx` | Review list + detail split | ~80 |
| `dashboard/src/components/review/ReviewList.tsx` | Pending review list | ~50 |
| `dashboard/src/components/review/ReviewDetail.tsx` | Markdown artifact viewer | ~70 |
| `dashboard/src/components/review/ReviewActions.tsx` | Approve/reject controls | ~60 |
| `dashboard/src/components/status/StatusPanel.tsx` | Project status overview | ~80 |
| `dashboard/src/components/status/AgentTable.tsx` | Active agents table | ~50 |
| `dashboard/src/components/notifications/NotificationsPanel.tsx` | Notification list | ~70 |
| `dashboard/src/components/notifications/NotificationItem.tsx` | Single notification | ~40 |
| `dashboard/src/components/questions/QuestionsPanel.tsx` | Q&A list + detail | ~80 |
| `dashboard/src/components/questions/QuestionDetail.tsx` | Question with options | ~60 |
| `dashboard/src/components/questions/AnswerForm.tsx` | Answer submission form | ~50 |
| **Total** | | **~1520** |
