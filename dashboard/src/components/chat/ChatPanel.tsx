/** Chat panel: conversational interface with Harmbe. */

import { useCallback, useEffect, useState } from "react";
import { useAppContext } from "../../context/AppContext";
import { api } from "../../services/api";
import type { ChatMessage } from "../../types/api";
import { MessageList } from "./MessageList";
import { ChatInput } from "./ChatInput";

export function ChatPanel() {
  const { activeProject } = useAppContext();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);

  const loadHistory = useCallback(async () => {
    setLoading(true);
    try {
      const history = await api.chat.history(activeProject ?? undefined);
      setMessages(history);
    } catch {
      // Silently fail on history load
    } finally {
      setLoading(false);
    }
  }, [activeProject]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  const handleSend = async (text: string) => {
    // Optimistic: add user message immediately
    const userMsg: ChatMessage = {
      message_id: `local-${Date.now()}`,
      role: "user",
      content: text,
      project_key: activeProject,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setSending(true);

    try {
      const response = await api.chat.send(text, activeProject ?? undefined);
      const assistantMsg: ChatMessage = {
        message_id: response.message_id,
        role: "assistant",
        content: response.response,
        project_key: activeProject,
        timestamp: response.timestamp,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      const errorMsg: ChatMessage = {
        message_id: `error-${Date.now()}`,
        role: "assistant",
        content: `Error: ${err instanceof Error ? err.message : "Failed to send message"}`,
        project_key: activeProject,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="flex h-full flex-col rounded-xl bg-white shadow-sm border border-gray-200 dark:bg-gray-800 dark:border-gray-700">
      <div className="border-b border-gray-200 px-6 py-3 dark:border-gray-700">
        <h2 className="text-base font-semibold text-gray-800 dark:text-gray-100">
          Chat with Harmbe
        </h2>
        {activeProject && (
          <p className="text-xs text-gray-400 dark:text-gray-500">
            Project: {activeProject}
          </p>
        )}
      </div>

      <div className="flex-1 overflow-hidden">
        {loading ? (
          <div className="flex h-full items-center justify-center text-sm text-gray-400 dark:text-gray-500">
            Loading history...
          </div>
        ) : (
          <MessageList messages={messages} />
        )}
      </div>

      <ChatInput onSend={handleSend} disabled={sending} />
    </div>
  );
}
