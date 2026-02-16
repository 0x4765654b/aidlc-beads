/** Root layout: sidebar + top nav + routed content area. */

import { Routes, Route, Navigate } from "react-router-dom";
import { Sidebar } from "./components/layout/Sidebar";
import { NavBar } from "./components/layout/NavBar";
import { ChatPanel } from "./components/chat/ChatPanel";
import { ReviewPanel } from "./components/review/ReviewPanel";
import { StatusPanel } from "./components/status/StatusPanel";
import { NotificationsPanel } from "./components/notifications/NotificationsPanel";
import { QuestionsPanel } from "./components/questions/QuestionsPanel";

export default function App() {
  return (
    <div className="flex h-screen overflow-hidden bg-gray-50 dark:bg-gray-950">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <NavBar />
        <main className="flex-1 overflow-auto bg-gray-50 p-6 dark:bg-gray-950">
          <Routes>
            <Route path="/" element={<Navigate to="/chat" replace />} />
            <Route path="/chat" element={<ChatPanel />} />
            <Route path="/review" element={<ReviewPanel />} />
            <Route path="/status" element={<StatusPanel />} />
            <Route path="/notifications" element={<NotificationsPanel />} />
            <Route path="/questions" element={<QuestionsPanel />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
