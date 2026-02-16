/** Typed REST client for the Orchestrator API. */

import type {
  CreateProjectRequest,
  ProjectResponse,
  ProjectStatusResponse,
  AgentResponse,
  ChatResponse,
  ChatMessage,
  ReviewGateResponse,
  ReviewDetailResponse,
  ReviewResultResponse,
  NotificationResponse,
  NotificationCountResponse,
  QuestionResponse,
  QuestionDetailResponse,
  AnswerResultResponse,
  SystemInfoResponse,
} from "../types/api";

const BASE_URL = import.meta.env.VITE_API_URL || "";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  health: () => request<{ status: string }>("/api/health"),
  info: () => request<SystemInfoResponse>("/api/info"),

  projects: {
    list: (status?: string) => {
      const qs = status ? `?status=${status}` : "";
      return request<ProjectResponse[]>(`/api/projects/${qs}`);
    },
    get: (key: string) => request<ProjectResponse>(`/api/projects/${key}`),
    create: (body: CreateProjectRequest) =>
      request<ProjectResponse>("/api/projects/", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    pause: (key: string) =>
      request<ProjectResponse>(`/api/projects/${key}/pause`, { method: "POST" }),
    resume: (key: string) =>
      request<ProjectResponse>(`/api/projects/${key}/resume`, {
        method: "POST",
      }),
    delete: (key: string) =>
      request<void>(`/api/projects/${key}`, { method: "DELETE" }),
    status: (key: string) =>
      request<ProjectStatusResponse>(`/api/projects/${key}/status`),
    agents: (key: string) =>
      request<AgentResponse[]>(`/api/projects/${key}/agents`),
  },

  chat: {
    send: (message: string, projectKey?: string) =>
      request<ChatResponse>("/api/chat/", {
        method: "POST",
        body: JSON.stringify({ message, project_key: projectKey }),
      }),
    history: (projectKey?: string, limit = 50) => {
      const params = new URLSearchParams();
      if (projectKey) params.set("project_key", projectKey);
      params.set("limit", String(limit));
      return request<ChatMessage[]>(`/api/chat/history?${params}`);
    },
  },

  review: {
    list: (projectKey?: string) => {
      const qs = projectKey ? `?project_key=${projectKey}` : "";
      return request<ReviewGateResponse[]>(`/api/review/${qs}`);
    },
    get: (issueId: string) =>
      request<ReviewDetailResponse>(`/api/review/${issueId}`),
    approve: (issueId: string, feedback = "") =>
      request<ReviewResultResponse>(`/api/review/${issueId}/approve`, {
        method: "POST",
        body: JSON.stringify({ feedback }),
      }),
    reject: (issueId: string, feedback: string) =>
      request<ReviewResultResponse>(`/api/review/${issueId}/reject`, {
        method: "POST",
        body: JSON.stringify({ feedback }),
      }),
  },

  notifications: {
    list: (projectKey?: string, limit = 20) => {
      const params = new URLSearchParams();
      if (projectKey) params.set("project_key", projectKey);
      params.set("limit", String(limit));
      return request<NotificationResponse[]>(`/api/notifications/?${params}`);
    },
    count: (projectKey?: string) => {
      const qs = projectKey ? `?project_key=${projectKey}` : "";
      return request<NotificationCountResponse>(
        `/api/notifications/count${qs}`
      );
    },
    markRead: (id: string) =>
      request<void>(`/api/notifications/${id}/read`, { method: "POST" }),
    markAllRead: (projectKey?: string) => {
      const qs = projectKey ? `?project_key=${projectKey}` : "";
      return request<{ marked: number }>(
        `/api/notifications/read-all${qs}`,
        { method: "POST" }
      );
    },
  },

  questions: {
    list: (projectKey?: string) => {
      const qs = projectKey ? `?project_key=${projectKey}` : "";
      return request<QuestionResponse[]>(`/api/questions/${qs}`);
    },
    get: (issueId: string) =>
      request<QuestionDetailResponse>(`/api/questions/${issueId}`),
    answer: (issueId: string, answer: string) =>
      request<AnswerResultResponse>(`/api/questions/${issueId}/answer`, {
        method: "POST",
        body: JSON.stringify({ answer }),
      }),
  },
};
