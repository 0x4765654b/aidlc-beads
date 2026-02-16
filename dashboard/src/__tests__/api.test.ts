/** Tests for the API client and types. */

import { describe, it, expect } from "vitest";
import type {
  ProjectResponse,
  ChatMessage,
  NotificationResponse,
  WebSocketEvent,
} from "../types/api";

describe("API Types", () => {
  it("ProjectResponse matches expected shape", () => {
    const project: ProjectResponse = {
      project_key: "test",
      name: "Test Project",
      workspace_path: "/dev/test",
      status: "active",
      minder_agent_id: null,
      created_at: "2026-02-15T00:00:00Z",
      paused_at: null,
    };
    expect(project.project_key).toBe("test");
    expect(project.status).toBe("active");
  });

  it("ChatMessage has user and assistant roles", () => {
    const userMsg: ChatMessage = {
      message_id: "msg-1",
      role: "user",
      content: "Hello",
      project_key: null,
      timestamp: "2026-02-15T00:00:00Z",
    };
    const assistantMsg: ChatMessage = {
      message_id: "msg-2",
      role: "assistant",
      content: "Hi!",
      project_key: null,
      timestamp: "2026-02-15T00:00:01Z",
    };
    expect(userMsg.role).toBe("user");
    expect(assistantMsg.role).toBe("assistant");
  });

  it("NotificationResponse has priority field", () => {
    const notif: NotificationResponse = {
      id: "notif-1",
      type: "review_gate",
      title: "Review Ready",
      body: "Requirements doc ready",
      project_key: "test",
      priority: 0,
      created_at: "2026-02-15T00:00:00Z",
      read: false,
      source_issue: "gt-12",
    };
    expect(notif.priority).toBe(0);
    expect(notif.read).toBe(false);
  });

  it("WebSocketEvent has required fields", () => {
    const event: WebSocketEvent = {
      event: "stage_completed",
      project_key: "test",
      data: { stage_name: "requirements-analysis" },
      timestamp: "2026-02-15T00:00:00Z",
    };
    expect(event.event).toBe("stage_completed");
    expect(event.data.stage_name).toBe("requirements-analysis");
  });
});

describe("API Client module", () => {
  it("exports api object", async () => {
    const { api } = await import("../services/api");
    expect(api).toBeDefined();
    expect(api.projects).toBeDefined();
    expect(api.chat).toBeDefined();
    expect(api.review).toBeDefined();
    expect(api.notifications).toBeDefined();
    expect(api.questions).toBeDefined();
    expect(api.health).toBeDefined();
    expect(api.info).toBeDefined();
  });

  it("api.projects has all methods", async () => {
    const { api } = await import("../services/api");
    expect(typeof api.projects.list).toBe("function");
    expect(typeof api.projects.get).toBe("function");
    expect(typeof api.projects.create).toBe("function");
    expect(typeof api.projects.pause).toBe("function");
    expect(typeof api.projects.resume).toBe("function");
    expect(typeof api.projects.delete).toBe("function");
    expect(typeof api.projects.status).toBe("function");
    expect(typeof api.projects.agents).toBe("function");
  });

  it("api.chat has all methods", async () => {
    const { api } = await import("../services/api");
    expect(typeof api.chat.send).toBe("function");
    expect(typeof api.chat.history).toBe("function");
  });

  it("api.notifications has all methods", async () => {
    const { api } = await import("../services/api");
    expect(typeof api.notifications.list).toBe("function");
    expect(typeof api.notifications.count).toBe("function");
    expect(typeof api.notifications.markRead).toBe("function");
    expect(typeof api.notifications.markAllRead).toBe("function");
  });
});
