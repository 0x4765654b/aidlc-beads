<!-- beads-issue: gt-67 -->
<!-- beads-review: gt-68 -->
# Unit 7: Harmbe Dashboard -- NFR Requirements

## 1. Usability

**NFR-UX-01**: The dashboard SHALL render correctly at viewport widths from 1024px to 2560px. Below 1024px, the sidebar collapses to an icon-only mode.

**NFR-UX-02**: All interactive elements (buttons, inputs, links) SHALL have visible focus indicators for keyboard navigation.

**NFR-UX-03**: The active panel SHALL be clearly indicated in the navigation (highlighted tab/icon).

**NFR-UX-04**: Loading states SHALL display a spinner or skeleton UI within 200ms of initiating a request.

**NFR-UX-05**: Error states SHALL display a human-readable message with a retry action. Raw error codes or stack traces SHALL NOT be shown to the user.

**NFR-UX-06**: The chat input SHALL support Enter-to-send and Shift+Enter for newlines.

**NFR-UX-07**: The notification badge SHALL be visible from every panel without requiring navigation.

**NFR-UX-08**: The review panel SHALL render markdown artifacts faithfully, including code blocks with syntax highlighting, headings, lists, and tables.

**NFR-UX-09**: Form validation errors (empty required fields, invalid inputs) SHALL appear inline next to the field, not as alert dialogs.

---

## 2. Responsiveness / Performance

**NFR-PERF-01**: Initial page load (first contentful paint) SHALL occur within 2 seconds on a localhost connection.

**NFR-PERF-02**: Panel navigation (client-side route change) SHALL complete within 200ms with no full-page reload.

**NFR-PERF-03**: WebSocket reconnection after a disconnect SHALL attempt within 2 seconds, with exponential backoff up to 30 seconds.

**NFR-PERF-04**: Chat message submission SHALL show the user's message instantly (optimistic UI) and display the response as it arrives.

**NFR-PERF-05**: Notification list SHALL render up to 100 items without visible scroll lag.

**NFR-PERF-06**: The JavaScript bundle (gzipped) SHALL be under 500KB for the initial load. Code splitting MAY be used for non-critical panels.

---

## 3. Reliability

**NFR-REL-01**: If the API server is unreachable, the dashboard SHALL display a connection status banner ("Offline -- reconnecting...") and retry automatically.

**NFR-REL-02**: If a WebSocket connection drops, in-flight data SHALL NOT be lost. On reconnection, the dashboard SHALL fetch the current state from REST endpoints to resynchronize.

**NFR-REL-03**: Submitting a review decision or Q&A answer SHALL disable the submit button during the request to prevent double-submission.

**NFR-REL-04**: Chat history SHALL survive panel switches within the same session (no re-fetch unless the project changes).

---

## 4. Accessibility

**NFR-A11Y-01**: All interactive elements SHALL be reachable via keyboard (Tab, Shift+Tab, Enter, Escape).

**NFR-A11Y-02**: Semantic HTML elements SHALL be used where appropriate: `<nav>`, `<main>`, `<aside>`, `<button>`, `<form>`.

**NFR-A11Y-03**: Color SHALL NOT be the sole indicator of state. Status indicators SHALL include text labels or icons alongside color.

**NFR-A11Y-04**: All images and icons SHALL have `alt` text or `aria-label` attributes.

---

## 5. Security

**NFR-SEC-01**: The dashboard SHALL NOT store secrets, API keys, or tokens in localStorage. For the initial local deployment, authentication is not required.

**NFR-SEC-02**: User-provided content (chat messages, feedback text) SHALL be sanitized before rendering to prevent XSS.

**NFR-SEC-03**: The dashboard SHALL communicate with the API over the same origin or a CORS-allowed origin only.

---

## 6. Maintainability

**NFR-MAINT-01**: Components SHALL be organized by feature domain (chat/, review/, status/, notifications/, questions/, layout/).

**NFR-MAINT-02**: Shared types matching API models SHALL be defined in a single `types.ts` file to avoid duplication.

**NFR-MAINT-03**: The API base URL SHALL be configurable via environment variable (`VITE_API_URL`), defaulting to `http://localhost:8000`.
