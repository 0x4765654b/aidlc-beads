/** Questions panel: view and answer pending Q&A questions. */

import { useCallback, useEffect, useState } from "react";
import { useAppContext } from "../../context/AppContext";
import { api } from "../../services/api";
import type { QuestionResponse } from "../../types/api";
import { AnswerForm } from "./AnswerForm";

export function QuestionsPanel() {
  const { activeProject } = useAppContext();
  const [questions, setQuestions] = useState<QuestionResponse[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const loadQuestions = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.questions.list(activeProject ?? undefined);
      setQuestions(data);
    } catch {
      // Graceful fallback
    } finally {
      setLoading(false);
    }
  }, [activeProject]);

  useEffect(() => {
    loadQuestions();
  }, [loadQuestions]);

  const handleAnswer = async (answer: string) => {
    if (!selected) return;
    try {
      const result = await api.questions.answer(selected, answer);
      setMessage(result.message);
      setSelected(null);
      loadQuestions();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to submit answer");
    }
  };

  const selectedQuestion = questions.find((q) => q.issue_id === selected);

  return (
    <div className="flex h-full flex-col rounded-xl bg-white shadow-sm border border-gray-200 dark:bg-gray-800 dark:border-gray-700">
      <div className="border-b border-gray-200 px-6 py-3 dark:border-gray-700">
        <h2 className="text-base font-semibold text-gray-800 dark:text-gray-100">
          Pending Questions ({questions.length})
        </h2>
      </div>

      {message && (
        <div className="mx-6 mt-3 rounded-md bg-green-50 px-4 py-2 text-sm text-green-700 dark:bg-green-900/30 dark:text-green-400">
          {message}
        </div>
      )}

      <div className="flex flex-1 overflow-hidden">
        {/* Question list */}
        <div className="w-64 flex-shrink-0 border-r border-gray-200 overflow-y-auto dark:border-gray-700">
          {loading ? (
            <p className="px-4 py-4 text-sm text-gray-400 dark:text-gray-500">Loading...</p>
          ) : questions.length === 0 ? (
            <p className="px-4 py-4 text-sm text-gray-400 dark:text-gray-500">
              No pending questions
            </p>
          ) : (
            <ul className="py-2">
              {questions.map((q) => (
                <li key={q.issue_id}>
                  <button
                    onClick={() => setSelected(q.issue_id)}
                    className={`w-full px-4 py-2.5 text-left text-sm transition-colors ${
                      selected === q.issue_id
                        ? "bg-gorilla-50 text-gorilla-800 font-medium dark:bg-gorilla-900/30 dark:text-gorilla-300"
                        : "text-gray-600 hover:bg-gray-50 dark:text-gray-400 dark:hover:bg-gray-700/50"
                    }`}
                  >
                    <p className="truncate">{q.title}</p>
                    <p className="text-[10px] text-gray-400 dark:text-gray-500">
                      [{q.issue_id}]
                    </p>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Question detail */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {selectedQuestion ? (
            <div>
              <h3 className="text-lg font-semibold text-gray-800 dark:text-gray-100">
                {selectedQuestion.title}
              </h3>
              <p className="mt-3 text-sm text-gray-600 whitespace-pre-wrap dark:text-gray-300">
                {selectedQuestion.description}
              </p>
              <div className="mt-6">
                <AnswerForm onSubmit={handleAnswer} />
              </div>
            </div>
          ) : (
            <p className="text-sm text-gray-400 dark:text-gray-500">
              Select a question to view details
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
