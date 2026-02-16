/** Single notification item with priority badge. */

import type { NotificationResponse } from "../../types/api";

const PRIORITY_COLORS: Record<number, string> = {
  0: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400",
  1: "bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-400",
  2: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400",
  3: "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400",
  4: "bg-gray-50 text-gray-500 dark:bg-gray-800 dark:text-gray-500",
};

const TYPE_LABELS: Record<string, string> = {
  review_gate: "Review",
  escalation: "Escalation",
  status_update: "Status",
  info: "Info",
  qa: "Question",
};

interface Props {
  notification: NotificationResponse;
  onMarkRead: (id: string) => void;
}

export function NotificationItem({ notification: n, onMarkRead }: Props) {
  return (
    <div
      className={`flex items-start gap-3 px-6 py-3 ${
        n.read ? "opacity-60" : ""
      }`}
    >
      <span
        className={`mt-1 inline-block h-2 w-2 flex-shrink-0 rounded-full ${
          n.read ? "bg-gray-300 dark:bg-gray-600" : "bg-gorilla-500"
        }`}
        aria-label={n.read ? "Read" : "Unread"}
      />

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span
            className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold ${
              PRIORITY_COLORS[n.priority] || PRIORITY_COLORS[4]
            }`}
          >
            P{n.priority}
          </span>
          <span className="text-[10px] text-gray-400 uppercase dark:text-gray-500">
            {TYPE_LABELS[n.type] || n.type}
          </span>
        </div>
        <p className="mt-0.5 text-sm font-medium text-gray-800 truncate dark:text-gray-100">
          {n.title}
        </p>
        <p className="text-xs text-gray-500 truncate dark:text-gray-400">{n.body}</p>
        <p className="mt-0.5 text-[10px] text-gray-400 dark:text-gray-500">
          {n.project_key} &middot;{" "}
          {new Date(n.created_at).toLocaleString()}
        </p>
      </div>

      {!n.read && (
        <button
          onClick={() => onMarkRead(n.id)}
          className="flex-shrink-0 text-xs text-gray-400 hover:text-gray-600 dark:text-gray-500 dark:hover:text-gray-300"
          aria-label="Mark as read"
        >
          Mark read
        </button>
      )}
    </div>
  );
}
