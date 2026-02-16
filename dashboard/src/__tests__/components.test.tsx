/** Component rendering tests for the Harmbe Dashboard. */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { AppProvider } from "../context/AppContext";
import { NavBar } from "../components/layout/NavBar";
import { ChatInput } from "../components/chat/ChatInput";
import { MessageBubble } from "../components/chat/MessageBubble";
import { AgentTable } from "../components/status/AgentTable";
import { NotificationItem } from "../components/notifications/NotificationItem";
import { AnswerForm } from "../components/questions/AnswerForm";
import type { ChatMessage, NotificationResponse, AgentResponse } from "../types/api";

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <BrowserRouter>
      <AppProvider>{children}</AppProvider>
    </BrowserRouter>
  );
}

describe("NavBar", () => {
  it("renders all navigation tabs", () => {
    render(
      <Wrapper>
        <NavBar />
      </Wrapper>
    );
    expect(screen.getByText("Chat")).toBeDefined();
    expect(screen.getByText("Review")).toBeDefined();
    expect(screen.getByText("Status")).toBeDefined();
    expect(screen.getByText("Questions")).toBeDefined();
    expect(screen.getByText("Notifications")).toBeDefined();
  });

  it("shows version text", () => {
    render(
      <Wrapper>
        <NavBar />
      </Wrapper>
    );
    expect(screen.getByText("Gorilla Troop v0.1.0")).toBeDefined();
  });
});

describe("ChatInput", () => {
  it("renders input and send button", () => {
    render(<ChatInput onSend={() => {}} />);
    expect(screen.getByPlaceholderText("Type a message...")).toBeDefined();
    expect(screen.getByText("Send")).toBeDefined();
  });

  it("disables send button when disabled prop is true", () => {
    render(<ChatInput onSend={() => {}} disabled />);
    expect(screen.getByText("Sending...")).toBeDefined();
  });
});

describe("MessageBubble", () => {
  it("renders user message", () => {
    const msg: ChatMessage = {
      message_id: "msg-1",
      role: "user",
      content: "Hello Harmbe!",
      project_key: null,
      timestamp: "2026-02-15T12:00:00Z",
    };
    render(<MessageBubble message={msg} />);
    expect(screen.getByText("Hello Harmbe!")).toBeDefined();
  });

  it("renders assistant message", () => {
    const msg: ChatMessage = {
      message_id: "msg-2",
      role: "assistant",
      content: "Hi there!",
      project_key: null,
      timestamp: "2026-02-15T12:00:01Z",
    };
    render(<MessageBubble message={msg} />);
    expect(screen.getByText("Hi there!")).toBeDefined();
  });
});

describe("AgentTable", () => {
  it("shows empty message when no agents", () => {
    render(<AgentTable agents={[]} />);
    expect(screen.getByText("No active agents")).toBeDefined();
  });

  it("renders agent rows", () => {
    const agents: AgentResponse[] = [
      {
        agent_id: "forge-abc",
        agent_type: "Forge",
        status: "running",
        current_task: "gt-43",
        created_at: "2026-02-15T12:00:00Z",
      },
    ];
    render(<AgentTable agents={agents} />);
    expect(screen.getByText("forge-abc")).toBeDefined();
    expect(screen.getByText("Forge")).toBeDefined();
    expect(screen.getByText("running")).toBeDefined();
    expect(screen.getByText("gt-43")).toBeDefined();
  });
});

describe("NotificationItem", () => {
  it("renders notification content", () => {
    const notif: NotificationResponse = {
      id: "notif-1",
      type: "review_gate",
      title: "Review Ready: Requirements",
      body: "Please review the requirements document.",
      project_key: "test-proj",
      priority: 0,
      created_at: "2026-02-15T12:00:00Z",
      read: false,
      source_issue: "gt-12",
    };
    render(<NotificationItem notification={notif} onMarkRead={() => {}} />);
    expect(screen.getByText("Review Ready: Requirements")).toBeDefined();
    expect(screen.getByText("Mark read")).toBeDefined();
  });

  it("does not show mark read for read notifications", () => {
    const notif: NotificationResponse = {
      id: "notif-2",
      type: "info",
      title: "Stage Done",
      body: "Stage completed.",
      project_key: "test-proj",
      priority: 3,
      created_at: "2026-02-15T12:00:00Z",
      read: true,
      source_issue: null,
    };
    render(<NotificationItem notification={notif} onMarkRead={() => {}} />);
    expect(screen.queryByText("Mark read")).toBeNull();
  });
});

describe("AnswerForm", () => {
  it("renders form elements", () => {
    render(<AnswerForm onSubmit={() => {}} />);
    expect(screen.getByText("Your Answer")).toBeDefined();
    expect(screen.getByText("Submit Answer")).toBeDefined();
    expect(
      screen.getByPlaceholderText("Type your answer or select an option...")
    ).toBeDefined();
  });
});
