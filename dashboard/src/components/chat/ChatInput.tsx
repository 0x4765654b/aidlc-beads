/** Chat input with Enter-to-send and Shift+Enter for newlines. */

import { useState, type KeyboardEvent, type FormEvent } from "react";

interface Props {
  onSend: (text: string) => void;
  disabled?: boolean;
}

export function ChatInput({ onSend, disabled = false }: Props) {
  const [text, setText] = useState("");

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText("");
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as unknown as FormEvent);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="border-t border-gray-200 px-4 py-3 dark:border-gray-700"
    >
      <div className="flex gap-2">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type a message..."
          rows={1}
          disabled={disabled}
          className="flex-1 resize-none rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-gorilla-500 focus:ring-1 focus:ring-gorilla-500 disabled:opacity-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:placeholder-gray-400"
        />
        <button
          type="submit"
          disabled={disabled || !text.trim()}
          className="rounded-lg bg-gorilla-600 px-4 py-2 text-sm font-medium text-white hover:bg-gorilla-700 disabled:opacity-50 transition-colors"
        >
          {disabled ? "Sending..." : "Send"}
        </button>
      </div>
    </form>
  );
}
