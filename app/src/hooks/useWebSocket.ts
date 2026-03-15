import { useCallback, useEffect, useRef, useState } from "react";
import type { WSMessage } from "../lib/types";

interface WebSocketState {
  messages: WSMessage[];
  isConnected: boolean;
  clearMessages: () => void;
}

const MAX_BUFFER = 5000;
const RECONNECT_DELAY_MS = 2000;

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isLogLevel(value: unknown): value is "INFO" | "WARN" | "ERROR" | "DEBUG" {
  return value === "INFO" || value === "WARN" || value === "ERROR" || value === "DEBUG";
}

function isWSMessage(value: unknown): value is WSMessage {
  if (!isObject(value) || typeof value.type !== "string") {
    return false;
  }

  if (value.type === "log") {
    return (
      isLogLevel(value.level) &&
      typeof value.message === "string" &&
      typeof value.timestamp === "string" &&
      (value.version === undefined || typeof value.version === "string")
    );
  }

  if (value.type === "progress") {
    return (
      typeof value.current === "number" &&
      typeof value.total === "number" &&
      typeof value.version_name === "string"
    );
  }

  if (value.type === "status") {
    return (
      typeof value.job_id === "string" &&
      (value.status === "pending" ||
        value.status === "running" ||
        value.status === "success" ||
        value.status === "failed" ||
        value.status === "cancelled")
    );
  }

  return false;
}

export function useWebSocket(url: string | null): WebSocketState {
  const [messages, setMessages] = useState<WSMessage[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearMessages = useCallback(() => {
    setMessages([]);
  }, []);

  useEffect(() => {
    if (!url) {
      return;
    }

    let cancelled = false;

    const connect = (): void => {
      if (cancelled) {
        return;
      }

      try {
        const ws = new WebSocket(url);
        wsRef.current = ws;

        ws.onopen = () => {
          if (!cancelled) {
            setIsConnected(true);
          }
        };

        ws.onmessage = (event) => {
          if (cancelled) {
            return;
          }

          try {
            const parsed: unknown = JSON.parse(event.data);
            if (isObject(parsed) && parsed.type === "ping") {
              return;
            }
            if (!isWSMessage(parsed)) {
              return;
            }
            setMessages((prev) => {
              const next = [...prev, parsed];
              return next.length > MAX_BUFFER ? next.slice(next.length - MAX_BUFFER) : next;
            });
          } catch {
            return;
          }
        };

        ws.onclose = () => {
          if (cancelled) {
            return;
          }

          setIsConnected(false);
          reconnectTimeoutRef.current = setTimeout(() => {
            if (!cancelled) {
              connect();
            }
          }, RECONNECT_DELAY_MS);
        };

        ws.onerror = () => {
          ws.close();
        };
      } catch {
        if (!cancelled) {
          reconnectTimeoutRef.current = setTimeout(() => {
            if (!cancelled) {
              connect();
            }
          }, RECONNECT_DELAY_MS);
        }
      }
    };

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }

      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }

      setIsConnected(false);
    };
  }, [url]);

  return { messages, isConnected, clearMessages };
}
