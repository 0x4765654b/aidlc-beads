/** Top navigation bar with panel tabs, notification badge, and dark mode toggle. */

import { NavLink } from "react-router-dom";
import { useAppContext } from "../../context/AppContext";

const TABS = [
  { to: "/chat", label: "Chat" },
  { to: "/review", label: "Review" },
  { to: "/status", label: "Status" },
  { to: "/questions", label: "Questions" },
  { to: "/notifications", label: "Notifications" },
];

function SunIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 20 20"
      fill="currentColor"
      className="h-3.5 w-3.5 text-amber-400"
    >
      <path d="M10 2a.75.75 0 01.75.75v1.5a.75.75 0 01-1.5 0v-1.5A.75.75 0 0110 2zM10 15a.75.75 0 01.75.75v1.5a.75.75 0 01-1.5 0v-1.5A.75.75 0 0110 15zM10 7a3 3 0 100 6 3 3 0 000-6zM15.657 5.404a.75.75 0 10-1.06-1.06l-1.061 1.06a.75.75 0 001.06 1.06l1.06-1.06zM6.464 14.596a.75.75 0 10-1.06-1.06l-1.061 1.06a.75.75 0 001.06 1.06l1.06-1.06zM18 10a.75.75 0 01-.75.75h-1.5a.75.75 0 010-1.5h1.5A.75.75 0 0118 10zM5 10a.75.75 0 01-.75.75h-1.5a.75.75 0 010-1.5h1.5A.75.75 0 015 10zM14.596 15.657a.75.75 0 001.06-1.06l-1.06-1.061a.75.75 0 10-1.06 1.06l1.06 1.06zM5.404 6.464a.75.75 0 001.06-1.06L5.404 4.344a.75.75 0 10-1.06 1.06l1.06 1.06z" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 20 20"
      fill="currentColor"
      className="h-3.5 w-3.5 text-indigo-300"
    >
      <path
        fillRule="evenodd"
        d="M7.455 2.004a.75.75 0 01.26.77 7 7 0 009.958 7.967.75.75 0 011.067.853A8.5 8.5 0 116.647 1.921a.75.75 0 01.808.083z"
        clipRule="evenodd"
      />
    </svg>
  );
}

export function NavBar() {
  const { unreadCount, darkMode, toggleDarkMode } = useAppContext();

  return (
    <header className="flex items-center justify-between border-b border-gray-200 bg-white px-6 py-0 dark:border-gray-700 dark:bg-gray-900">
      <nav className="flex gap-1" aria-label="Main navigation">
        {TABS.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            className={({ isActive }) =>
              `relative px-4 py-3 text-sm font-medium transition-colors border-b-2 ${
                isActive
                  ? "border-gorilla-600 text-gorilla-700 dark:border-gorilla-400 dark:text-gorilla-400"
                  : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-200 dark:hover:border-gray-500"
              }`
            }
          >
            {tab.label}
            {tab.to === "/notifications" && unreadCount > 0 && (
              <span className="absolute -top-0.5 right-0.5 flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">
                {unreadCount > 99 ? "99+" : unreadCount}
              </span>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="flex items-center gap-4">
        {/* Dark mode toggle slider */}
        <button
          onClick={toggleDarkMode}
          className="group relative flex h-6 w-11 items-center rounded-full bg-gray-200 transition-colors dark:bg-gray-600"
          role="switch"
          aria-checked={darkMode}
          aria-label="Toggle dark mode"
        >
          <span
            className={`absolute flex h-5 w-5 items-center justify-center rounded-full bg-white shadow-sm transition-transform duration-200 ${
              darkMode ? "translate-x-5.5" : "translate-x-0.5"
            }`}
          >
            {darkMode ? <MoonIcon /> : <SunIcon />}
          </span>
        </button>

        <span className="text-xs text-gray-400 dark:text-gray-500">
          Gorilla Troop v0.1.0
        </span>
      </div>
    </header>
  );
}
