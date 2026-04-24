import type { ChatSpec } from "@/api/types/chat";
import type { IAgentScopeRuntimeWebUISession } from "@/components/agentscope-chat";

export type HistorySession = IAgentScopeRuntimeWebUISession & {
  createdAt?: string | null;
  meta?: Record<string, unknown>;
  realId?: string;
};

export function getHistorySessionTargetId(session: HistorySession): string {
  return session.realId || session.id || "";
}

export function isHistorySessionActive(
  session: HistorySession | undefined,
  currentChatId: string | null | undefined,
): boolean {
  if (!session || !currentChatId) {
    return false;
  }

  return session.id === currentChatId || session.realId === currentChatId;
}

export function buildHistorySessions(chats: ChatSpec[]): HistorySession[] {
  return [...chats]
    .reverse()
    .filter((chat) => chat.meta?.session_kind !== "task")
    .map((chat) => ({
      id: chat.id,
      name: chat.name || "新会话",
      messages: [],
      meta: chat.meta,
      createdAt: chat.created_at,
    }));
}
