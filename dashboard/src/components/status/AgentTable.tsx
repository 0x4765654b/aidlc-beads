/** Active agents table. */

import type { AgentResponse } from "../../types/api";

interface Props {
  agents: AgentResponse[];
}

export function AgentTable({ agents }: Props) {
  if (agents.length === 0) {
    return <p className="text-sm text-gray-400 dark:text-gray-500">No active agents</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200 text-left text-xs font-medium text-gray-500 uppercase tracking-wider dark:border-gray-700 dark:text-gray-400">
            <th className="pb-2 pr-4">Agent</th>
            <th className="pb-2 pr-4">Type</th>
            <th className="pb-2 pr-4">Status</th>
            <th className="pb-2">Task</th>
          </tr>
        </thead>
        <tbody>
          {agents.map((a) => (
            <tr key={a.agent_id} className="border-b border-gray-100 dark:border-gray-700/50">
              <td className="py-2 pr-4 font-mono text-xs text-gray-600 dark:text-gray-400">
                {a.agent_id}
              </td>
              <td className="py-2 pr-4 dark:text-gray-300">{a.agent_type}</td>
              <td className="py-2 pr-4">
                <span
                  className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                    a.status === "running"
                      ? "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400"
                      : a.status === "starting"
                      ? "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-400"
                      : "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400"
                  }`}
                >
                  {a.status}
                </span>
              </td>
              <td className="py-2 font-mono text-xs text-gray-500 dark:text-gray-400">
                {a.current_task || "-"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
