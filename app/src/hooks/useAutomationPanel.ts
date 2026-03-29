import { useCallback, useEffect, useRef } from "react";
import type { WSMessage } from "../lib/types";
import type { useAutomation } from "./useAutomation";
import type { useWebSocket } from "./useWebSocket";

type UseAutomationReturn = ReturnType<typeof useAutomation>;
type UseWebSocketReturn = ReturnType<typeof useWebSocket>;

type LogState = {
  messages: WSMessage[];
  isConnected: boolean;
  clearMessages: () => void;
};

type UseAutomationPanelParams = {
  ws: UseWebSocketReturn;
  automation: UseAutomationReturn;
  sidecarUrl: string | null | undefined;
  onLogStateChange?: (state: LogState) => void;
  onMessage?: (message: WSMessage) => void;
  includePolledMessagesWhenNoWsLogs?: boolean;
};

type UseAutomationPanelResult = {
  hasConnectedRef: React.MutableRefObject<boolean>;
  resetProcessedCount: () => void;
  resetTracking: () => void;
};

export function useAutomationPanel({
  ws,
  automation,
  sidecarUrl,
  onLogStateChange,
  onMessage,
  includePolledMessagesWhenNoWsLogs = false,
}: UseAutomationPanelParams): UseAutomationPanelResult {
  const processedCountRef = useRef(0);
  const hasConnectedRef = useRef(false);

  const resetProcessedCount = useCallback(() => {
    processedCountRef.current = 0;
  }, []);

  const resetTracking = useCallback(() => {
    processedCountRef.current = 0;
    hasConnectedRef.current = false;
  }, []);

  useEffect(() => {
    if (ws.isConnected) {
      hasConnectedRef.current = true;
    }
  }, [ws.isConnected]);

  useEffect(() => {
    const newMessages = ws.messages.slice(processedCountRef.current);
    newMessages.forEach((message) => {
      automation.handleMessage(message);
      onMessage?.(message);
    });
    processedCountRef.current = ws.messages.length;
  }, [ws.messages, automation.handleMessage, onMessage]);

  useEffect(() => {
    if (!automation.isRunning || !automation.jobId || !sidecarUrl) {
      return;
    }

    const pollUrl = sidecarUrl;
    const jobId = automation.jobId;

    const interval = setInterval(() => {
      void automation.pollJobStatus(pollUrl, jobId);
    }, 2000);

    return () => clearInterval(interval);
  }, [automation.isRunning, automation.jobId, sidecarUrl, automation.pollJobStatus]);

  useEffect(() => {
    if (!onLogStateChange) {
      return;
    }

    const wsLogCount = ws.messages.filter((message) => message.type === "log").length;
    const messages =
      includePolledMessagesWhenNoWsLogs && wsLogCount === 0
        ? [...ws.messages, ...automation.polledMessages]
        : ws.messages;

    onLogStateChange({
      messages,
      isConnected: ws.isConnected,
      clearMessages: ws.clearMessages,
    });
  }, [
    ws.messages,
    ws.isConnected,
    ws.clearMessages,
    onLogStateChange,
    includePolledMessagesWhenNoWsLogs,
    automation.polledMessages,
  ]);

  return { hasConnectedRef, resetProcessedCount, resetTracking };
}
