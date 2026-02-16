/** Project sidebar: project list with status indicators. */

import { useEffect, useState } from "react";
import { useAppContext } from "../../context/AppContext";
import { api } from "../../services/api";
import type { ProjectResponse } from "../../types/api";
import { NewProjectDialog } from "./NewProjectDialog";

const STATUS_COLORS: Record<string, string> = {
  active: "bg-green-500",
  paused: "bg-gray-400",
  completed: "bg-gray-300",
};

export function Sidebar() {
  const { activeProject, setActiveProject } = useAppContext();
  const [projects, setProjects] = useState<ProjectResponse[]>([]);
  const [showDialog, setShowDialog] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      const data = await api.projects.list();
      setProjects(data);
      setError(null);
    } catch {
      setError("Failed to load projects");
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <aside className="flex w-60 flex-col border-r border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-900">
      <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3 dark:border-gray-700">
        <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wider dark:text-gray-300">
          Projects
        </h2>
      </div>

      <nav className="flex-1 overflow-y-auto px-2 py-2" aria-label="Projects">
        {error && (
          <p className="px-2 py-1 text-xs text-red-500">{error}</p>
        )}
        {projects.map((p) => (
          <button
            key={p.project_key}
            onClick={() => setActiveProject(p.project_key)}
            className={`flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm transition-colors ${
              activeProject === p.project_key
                ? "bg-gorilla-100 text-gorilla-800 font-medium dark:bg-gorilla-900/40 dark:text-gorilla-300"
                : "text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800"
            }`}
          >
            <span
              className={`inline-block h-2 w-2 rounded-full ${
                STATUS_COLORS[p.status] || "bg-gray-300"
              }`}
              aria-label={p.status}
            />
            <span className="truncate">{p.name}</span>
          </button>
        ))}
      </nav>

      <div className="border-t border-gray-200 p-3 dark:border-gray-700">
        <button
          onClick={() => setShowDialog(true)}
          className="w-full rounded-md bg-gorilla-600 px-3 py-2 text-sm font-medium text-white hover:bg-gorilla-700 transition-colors"
        >
          + New Project
        </button>
      </div>

      {showDialog && (
        <NewProjectDialog
          onClose={() => setShowDialog(false)}
          onCreated={() => {
            setShowDialog(false);
            load();
          }}
        />
      )}
    </aside>
  );
}
