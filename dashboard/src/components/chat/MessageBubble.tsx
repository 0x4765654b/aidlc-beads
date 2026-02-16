/** Single chat message bubble (user or assistant). */

import type { ChatMessage } from "../../types/api";

interface Props {
  message: ChatMessage;
}

export function MessageBubble({ message }: Props) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[75%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
          isUser
            ? "bg-gorilla-600 text-white"
            : "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-100"
        }`}
      >
        <p className="whitespace-pre-wrap break-words">{message.content}</p>
        <p
          className={`mt-1 text-[10px] ${
            isUser ? "text-gorilla-100" : "text-gray-400 dark:text-gray-500"
          }`}
        >
          {new Date(message.timestamp).toLocaleTimeString()}
        </p>
      </div>
    </div>
  );
}
