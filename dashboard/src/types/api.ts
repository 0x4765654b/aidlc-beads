/** Shared TypeScript types matching the Orchestrator API Pydantic models. */

// ── Projects ──────────────────────────────────────────────────────

export interface CreateProjectRequest {
  key: string;
  name: string;
  workspace_path: string;
}

export interface ProjectResponse {
  project_key: string;
  name: string;
  workspace_path: string;
  status: string;
  minder_agent_id: string | null;
  created_at: string;
  paused_at: string | null;
}

export interface ProjectStatusResponse {
  project_key: string;
  name: string;
  status: string;
  current_phase: string;
  active_agents: number;
  pending_reviews: number;
  open_questions: number;
  ready_issues: Record<string, unknown>[];
  in_progress_issues: Record<string, unknown>[];
}

export interface AgentResponse {
  agent_id: string;
  agent_type: string;
  status: string;
  current_task: string | null;
  created_at: string;
}

// ── Chat ──────────────────────────────────────────────────────────

export interface ChatRequest {
  message: string;
  project_key?: string | null;
}

export interface ChatResponse {
  message_id: string;
  response: string;
  project_key: string | null;
  actions_taken: string[];
  timestamp: string;
}

export interface ChatMessage {
  message_id: string;
  role: "user" | "assistant";
  content: string;
  project_key: string | null;
  timestamp: string;
}

// ── Review ────────────────────────────────────────────────────────

export interface ReviewGateResponse {
  issue_id: string;
  title: string;
  project_key: string;
  stage_name: string;
  artifact_path: string | null;
  created_at: string;
  status: string;
}

export interface ReviewDetailResponse {
  issue_id: string;
  title: string;
  project_key: string;
  stage_name: string;
  artifact_path: string | null;
  artifact_content: string | null;
  status: string;
  notes: string | null;
}

export interface ReviewDecision {
  feedback: string;
  edited_content?: string | null;
}

export interface ReviewResultResponse {
  issue_id: string;
  decision: string;
  next_action: string;
  message: string;
}

// ── Notifications ─────────────────────────────────────────────────

export interface NotificationResponse {
  id: string;
  type: string;
  title: string;
  body: string;
  project_key: string;
  priority: number;
  created_at: string;
  read: boolean;
  source_issue: string | null;
}

export interface NotificationCountResponse {
  count: number;
  by_type: Record<string, number>;
}

// ── Questions ─────────────────────────────────────────────────────

export interface QuestionResponse {
  issue_id: string;
  title: string;
  project_key: string;
  description: string;
  stage_name: string | null;
  created_at: string;
  status: string;
}

export interface QuestionDetailResponse {
  issue_id: string;
  title: string;
  project_key: string;
  description: string;
  options: string[];
  stage_name: string | null;
  blocking_issue: string | null;
  created_at: string;
}

export interface AnswerRequest {
  answer: string;
}

export interface AnswerResultResponse {
  issue_id: string;
  answer: string;
  unblocked_stages: string[];
  message: string;
}

// ── System ────────────────────────────────────────────────────────

export interface SystemInfoResponse {
  version: string;
  active_projects: number;
  active_agents: number;
  pending_notifications: number;
  engine_status: string;
}

// ── WebSocket ─────────────────────────────────────────────────────

export interface WebSocketEvent {
  event: string;
  project_key: string;
  data: Record<string, unknown>;
  timestamp: string;
}
