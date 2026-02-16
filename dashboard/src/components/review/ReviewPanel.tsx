/** Review panel: list pending review gates, view artifacts, approve/reject. */

import { useCallback, useEffect, useState } from "react";
import { useAppContext } from "../../context/AppContext";
import { api } from "../../services/api";
import type { ReviewGateResponse } from "../../types/api";

export function ReviewPanel() {
  const { activeProject } = useAppContext();
  const [reviews, setReviews] = useState<ReviewGateResponse[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [feedback, setFeedback] = useState("");
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const loadReviews = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.review.list(activeProject ?? undefined);
      setReviews(data);
    } catch {
      // Graceful fallback
    } finally {
      setLoading(false);
    }
  }, [activeProject]);

  useEffect(() => {
    loadReviews();
  }, [loadReviews]);

  const handleApprove = async () => {
    if (!selected) return;
    setActionLoading(true);
    try {
      const result = await api.review.approve(selected, feedback);
      setMessage(result.message);
      setSelected(null);
      setFeedback("");
      loadReviews();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to approve");
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async () => {
    if (!selected || !feedback.trim()) return;
    setActionLoading(true);
    try {
      const result = await api.review.reject(selected, feedback);
      setMessage(result.message);
      setSelected(null);
      setFeedback("");
      loadReviews();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to reject");
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="flex h-full flex-col rounded-xl bg-white shadow-sm border border-gray-200 dark:bg-gray-800 dark:border-gray-700">
      <div className="border-b border-gray-200 px-6 py-3 dark:border-gray-700">
        <h2 className="text-base font-semibold text-gray-800 dark:text-gray-100">
          Pending Reviews ({reviews.length})
        </h2>
      </div>

      {message && (
        <div className="mx-6 mt-3 rounded-md bg-green-50 px-4 py-2 text-sm text-green-700 dark:bg-green-900/30 dark:text-green-400">
          {message}
        </div>
      )}

      <div className="flex-1 overflow-y-auto px-6 py-4">
        {loading ? (
          <p className="text-sm text-gray-400 dark:text-gray-500">Loading...</p>
        ) : reviews.length === 0 ? (
          <p className="text-sm text-gray-400 dark:text-gray-500">No pending reviews</p>
        ) : (
          <ul className="space-y-2">
            {reviews.map((r) => (
              <li key={r.issue_id}>
                <button
                  onClick={() => setSelected(r.issue_id)}
                  className={`w-full rounded-lg px-4 py-3 text-left text-sm transition-colors ${
                    selected === r.issue_id
                      ? "bg-gorilla-50 border border-gorilla-300 dark:bg-gorilla-900/30 dark:border-gorilla-600"
                      : "bg-gray-50 hover:bg-gray-100 border border-transparent dark:bg-gray-700/50 dark:hover:bg-gray-700"
                  }`}
                >
                  <span className="font-medium text-gray-800 dark:text-gray-100">{r.title}</span>
                  <span className="ml-2 text-xs text-gray-400 dark:text-gray-500">
                    [{r.issue_id}]
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {selected && (
        <div className="border-t border-gray-200 px-6 py-4 space-y-3 dark:border-gray-700">
          <textarea
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder="Feedback (required for reject)..."
            rows={3}
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-gorilla-500 focus:ring-1 focus:ring-gorilla-500 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:placeholder-gray-400"
          />
          <div className="flex gap-3">
            <button
              onClick={handleApprove}
              disabled={actionLoading}
              className="rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
            >
              Approve
            </button>
            <button
              onClick={handleReject}
              disabled={actionLoading || !feedback.trim()}
              className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
            >
              Request Changes
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
