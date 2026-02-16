/** Notifications panel: prioritized list of human-attention items. */

import { useCallback, useEffect, useState } from "react";
import { useAppContext } from "../../context/AppContext";
import { api } from "../../services/api";
import type { NotificationResponse } from "../../types/api";
import { NotificationItem } from "./NotificationItem";

export function NotificationsPanel() {
  const { activeProject, unreadCount, setUnreadCount } = useAppContext();
  const [notifications, setNotifications] = useState<NotificationResponse[]>(
    []
  );
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.notifications.list(
        activeProject ?? undefined,
        50
      );
      setNotifications(data);
      const count = await api.notifications.count(
        activeProject ?? undefined
      );
      setUnreadCount(count.count);
    } catch {
      // Graceful fallback
    } finally {
      setLoading(false);
    }
  }, [activeProject, setUnreadCount]);

  useEffect(() => {
    load();
  }, [load]);

  const handleMarkRead = async (id: string) => {
    try {
      await api.notifications.markRead(id);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, read: true } : n))
      );
      setUnreadCount(Math.max(0, unreadCount - 1));
    } catch {
      // Ignore
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await api.notifications.markAllRead(activeProject ?? undefined);
      setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
      setUnreadCount(0);
    } catch {
      // Ignore
    }
  };

  return (
    <div className="rounded-xl bg-white shadow-sm border border-gray-200 dark:bg-gray-800 dark:border-gray-700">
      <div className="flex items-center justify-between border-b border-gray-200 px-6 py-3 dark:border-gray-700">
        <h2 className="text-base font-semibold text-gray-800 dark:text-gray-100">
          Notifications
        </h2>
        <button
          onClick={handleMarkAllRead}
          className="text-xs text-gorilla-600 hover:text-gorilla-700 font-medium dark:text-gorilla-400 dark:hover:text-gorilla-300"
        >
          Mark All Read
        </button>
      </div>

      <div className="divide-y divide-gray-100 dark:divide-gray-700/50">
        {loading ? (
          <p className="px-6 py-8 text-sm text-gray-400 dark:text-gray-500">Loading...</p>
        ) : notifications.length === 0 ? (
          <p className="px-6 py-8 text-sm text-gray-400 dark:text-gray-500">
            No notifications
          </p>
        ) : (
          notifications.map((n) => (
            <NotificationItem
              key={n.id}
              notification={n}
              onMarkRead={handleMarkRead}
            />
          ))
        )}
      </div>
    </div>
  );
}
