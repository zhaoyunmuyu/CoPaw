import dayjs from "dayjs";
import type {
  IAgentScopeRuntimeRequest,
  IAgentScopeRuntimeResponse,
} from "@/components/agentscope-chat/AgentScopeRuntimeWebUI/core/AgentScopeRuntime/types";

export interface ChatMessageHeaderMeta {
  timestamp?: number;
}

export interface ChatRuntimeRequestCardData
  extends IAgentScopeRuntimeRequest {
  headerMeta?: ChatMessageHeaderMeta;
}

export interface ChatRuntimeResponseCardData
  extends IAgentScopeRuntimeResponse {
  headerMeta?: ChatMessageHeaderMeta;
}

type TimestampSource = {
  timestamp?: unknown;
};

function normalizeEpochMs(value: number): number {
  return value < 1_000_000_000_000 ? value * 1000 : value;
}

function toTimestamp(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return normalizeEpochMs(value);
  }

  if (typeof value !== "string") return null;

  const trimmed = value.trim();
  if (!trimmed) return null;

  const numeric = Number(trimmed);
  if (Number.isFinite(numeric)) {
    return normalizeEpochMs(numeric);
  }

  const parsed = Date.parse(trimmed);
  return Number.isNaN(parsed) ? null : parsed;
}

export function resolveMessageTimestamp(
  message: TimestampSource,
): number | undefined {
  return toTimestamp(message.timestamp) ?? undefined;
}

export function resolveGroupTimestamp(
  messages: TimestampSource[],
): number | undefined {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const resolved = resolveMessageTimestamp(messages[index]);
    if (resolved) return resolved;
  }

  return undefined;
}

export function formatMessageTime(timestamp?: number): string {
  if (timestamp === undefined) return "";
  return dayjs(timestamp).format("MM-DD HH:mm");
}
