/** Scrollable message list with auto-scroll to bottom. */

import { useEffect, useRef } from "react";
import type { ChatMessage } from "../../types/api";
import { MessageBubble } from "./MessageBubble";

interface Props {
  messages: ChatMessage[];
}

export function MessageList({ messages }: Props) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  if (messages.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-gray-400 dark:text-gray-500">
        Start a conversation with Harmbe
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto px-6 py-4 space-y-3">
      {messages.map((msg) => (
        <MessageBubble key={msg.message_id} message={msg} />
      ))}
      <div ref={endRef} />
    </div>
  );
}
