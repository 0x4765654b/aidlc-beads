/** Project status panel: overview of workflow, agents, issues. */

import { useCallback, useEffect, useState } from "react";
import { useAppContext } from "../../context/AppContext";
import { api } from "../../services/api";
import type { ProjectStatusResponse, AgentResponse } from "../../types/api";
import { AgentTable } from "./AgentTable";

export function StatusPanel() {
  const { activeProject } = useAppContext();
  const [status, setStatus] = useState<ProjectStatusResponse | null>(null);
  const [agents, setAgents] = useState<AgentResponse[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!activeProject) return;
    try {
      const [s, a] = await Promise.all([
        api.projects.status(activeProject),
        api.projects.agents(activeProject),
      ]);
      setStatus(s);
      setAgents(a);
      setError(null);
    } catch {
      setError("Failed to load project status");
    }
  }, [activeProject]);

  useEffect(() => {
    load();
  }, [load]);

  if (!activeProject) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-gray-400 dark:text-gray-500">
        Select a project from the sidebar
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="rounded-xl bg-white p-6 shadow-sm border border-gray-200 dark:bg-gray-800 dark:border-gray-700">
        <h2 className="text-base font-semibold text-gray-800 dark:text-gray-100">
          {status?.name || activeProject}
        </h2>
        {error && <p className="mt-2 text-sm text-red-500">{error}</p>}
        {status && (
          <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Stat label="Status" value={status.status} />
            <Stat label="Phase" value={status.current_phase} />
            <Stat label="Active Agents" value={String(status.active_agents)} />
            <Stat
              label="Pending Reviews"
              value={String(status.pending_reviews)}
            />
          </div>
        )}
      </div>

      <div className="rounded-xl bg-white p-6 shadow-sm border border-gray-200 dark:bg-gray-800 dark:border-gray-700">
        <h3 className="text-sm font-semibold text-gray-700 mb-3 dark:text-gray-300">
          Active Agents
        </h3>
        <AgentTable agents={agents} />
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs font-medium text-gray-500 uppercase tracking-wider dark:text-gray-400">
        {label}
      </p>
      <p className="mt-1 text-lg font-semibold text-gray-800 dark:text-gray-100">{value}</p>
    </div>
  );
}
