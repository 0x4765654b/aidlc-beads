/** App-wide state context: active project, unread notification count, dark mode. */

import {
  createContext,
  useContext,
  useState,
  useEffect,
  type ReactNode,
} from "react";

interface AppState {
  activeProject: string | null;
  setActiveProject: (key: string | null) => void;
  unreadCount: number;
  setUnreadCount: (count: number) => void;
  darkMode: boolean;
  toggleDarkMode: () => void;
}

const AppContext = createContext<AppState | undefined>(undefined);

function getInitialDarkMode(): boolean {
  try {
    const stored = localStorage.getItem("gt-dark-mode");
    if (stored !== null) return stored === "true";
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  } catch {
    return false;
  }
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [activeProject, setActiveProject] = useState<string | null>(null);
  const [unreadCount, setUnreadCount] = useState(0);
  const [darkMode, setDarkMode] = useState(getInitialDarkMode);

  useEffect(() => {
    const root = document.documentElement;
    if (darkMode) {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }
    try {
      localStorage.setItem("gt-dark-mode", String(darkMode));
    } catch {
      // localStorage unavailable in test environments
    }
  }, [darkMode]);

  const toggleDarkMode = () => setDarkMode((prev) => !prev);

  return (
    <AppContext.Provider
      value={{
        activeProject,
        setActiveProject,
        unreadCount,
        setUnreadCount,
        darkMode,
        toggleDarkMode,
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useAppContext(): AppState {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useAppContext must be inside AppProvider");
  return ctx;
}
