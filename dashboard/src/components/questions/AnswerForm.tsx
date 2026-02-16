/** Answer submission form for Q&A questions. */

import { useState, type FormEvent } from "react";

interface Props {
  onSubmit: (answer: string) => void;
}

export function AnswerForm({ onSubmit }: Props) {
  const [answer, setAnswer] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!answer.trim()) return;
    setSubmitting(true);
    try {
      onSubmit(answer.trim());
      setAnswer("");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
        Your Answer
      </label>
      <textarea
        value={answer}
        onChange={(e) => setAnswer(e.target.value)}
        placeholder="Type your answer or select an option..."
        rows={3}
        className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-gorilla-500 focus:ring-1 focus:ring-gorilla-500 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:placeholder-gray-400"
      />
      <button
        type="submit"
        disabled={submitting || !answer.trim()}
        className="rounded-md bg-gorilla-600 px-4 py-2 text-sm font-medium text-white hover:bg-gorilla-700 disabled:opacity-50"
      >
        {submitting ? "Submitting..." : "Submit Answer"}
      </button>
    </form>
  );
}
