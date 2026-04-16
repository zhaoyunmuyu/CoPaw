import type { ChatSpec } from "@/api/types/chat";
import type { IAgentScopeRuntimeWebUISession } from "@/components/agentscope-chat";

export type HistorySession = IAgentScopeRuntimeWebUISession & {
  createdAt?: string | null;
  meta?: Record<string, unknown>;
};

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
