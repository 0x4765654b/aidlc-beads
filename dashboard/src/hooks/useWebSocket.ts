/** WebSocket hook with automatic reconnection and event subscription. */

import { useCallback, useEffect, useRef, useState } from "react";
import type { WebSocketEvent } from "../types/api";

const INITIAL_DELAY = 1000;
const MAX_DELAY = 30000;
const BACKOFF_FACTOR = 2;

type EventHandler = (data: Record<string, unknown>) => void;

export function useWebSocket(projectKey = "all") {
  const [isConnected, setIsConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<WebSocketEvent | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const subscribersRef = useRef<Map<string, Set<EventHandler>>>(new Map());
  const reconnectDelay = useRef(INITIAL_DELAY);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isMounted = useRef(true);

  const connect = useCallback(() => {
    if (!isMounted.current) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl =
      import.meta.env.VITE_WS_URL ||
      `${protocol}//${window.location.host}/ws?project_key=${projectKey}`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!isMounted.current) return;
      setIsConnected(true);
      reconnectDelay.current = INITIAL_DELAY;

      // Notify subscribers of reconnection so they can resync
      const handlers = subscribersRef.current.get("_reconnected");
      handlers?.forEach((h) => h({}));
    };

    ws.onmessage = (event) => {
      if (!isMounted.current) return;
      try {
        const parsed: WebSocketEvent = JSON.parse(event.data);
        setLastEvent(parsed);
        const handlers = subscribersRef.current.get(parsed.event);
        handlers?.forEach((h) => h(parsed.data));
      } catch {
        // Ignore malformed messages
      }
    };

    ws.onclose = () => {
      if (!isMounted.current) return;
      setIsConnected(false);
      scheduleReconnect();
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [projectKey]);

  const scheduleReconnect = useCallback(() => {
    if (!isMounted.current) return;
    if (reconnectTimer.current) clearTimeout(reconnectTimer.current);

    reconnectTimer.current = setTimeout(() => {
      reconnectDelay.current = Math.min(
        reconnectDelay.current * BACKOFF_FACTOR,
        MAX_DELAY
      );
      connect();
    }, reconnectDelay.current);
  }, [connect]);

  useEffect(() => {
    isMounted.current = true;
    connect();
    return () => {
      isMounted.current = false;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const subscribe = useCallback(
    (eventType: string, handler: EventHandler): (() => void) => {
      if (!subscribersRef.current.has(eventType)) {
        subscribersRef.current.set(eventType, new Set());
      }
      subscribersRef.current.get(eventType)!.add(handler);

      return () => {
        subscribersRef.current.get(eventType)?.delete(handler);
      };
    },
    []
  );

  return { lastEvent, isConnected, subscribe };
}
