// ==================== 组件引入方式变更 (Kun He) ====================
import {
  IAgentScopeRuntimeWebUISession,
  IAgentScopeRuntimeWebUISessionAPI,
  IAgentScopeRuntimeWebUIMessage,
} from "@/components/agentscope-chat";
// ==================== 组件引入方式变更结束 ====================
import api, {
  type ChatSpec,
  type ChatHistory,
  type ChatStatus,
  type Message,
} from "../../../api";
import { cronJobApi } from "../../../api/modules/cronjob";
import type {
  ChatApprovalActionCardData,
  ChatRuntimeRequestCardData,
  ChatRuntimeResponseCardData,
} from "../messageMeta";
import { resolveGroupTimestamp, resolveMessageTimestamp } from "../messageMeta";
import { toDisplayUrl } from "../utils";
import { applyPreferredSessionSelection } from "./preferredSession";
import { shouldNotifySessionSelected } from "./sessionRaceGuard";
import { filterStaleTaskSessions } from "./taskSessions";
import {
  forgetResolvedChatId,
  forgetResolvedChatIdsForChat,
  getResolvedChatId,
  rememberResolvedChatId,
} from "./resolvedSessionMapping";

// ==================== userId 统一整改 (Kun He) ====================
// 使用统一的 getUserId/getChannel helper
import {
  getUserId,
  getChannel,
  getUserIdWithoutWindow,
  getChannelWithoutWindow,
} from "../../../utils/identity";
// ==================== userId 统一整改结束 ====================

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_SESSION_NAME = "新会话";
const ROLE_TOOL = "tool";
const ROLE_USER = "user";
const ROLE_ASSISTANT = "assistant";
const TYPE_PLUGIN_CALL_OUTPUT = "plugin_call_output";
// const CARD_REQUEST = "AgentScopeRuntimeRequestCard";
const CARD_RESPONSE = "AgentScopeRuntimeResponseCard";
const CARD_APPROVAL_ACTION = "ApprovalAction";

// ---------------------------------------------------------------------------
// Window globals
// ---------------------------------------------------------------------------

interface CustomWindow extends Window {
  currentSessionId?: string;
  currentUserId?: string;
  currentChannel?: string;
}

declare const window: CustomWindow;

// ---------------------------------------------------------------------------
// Local helper types
// ---------------------------------------------------------------------------

/** A single item inside a message's content array. */
interface ContentItem {
  type: string;
  text?: string;
  [key: string]: unknown;
}

/** A backend message after role-normalisation (output of toOutputMessage). */
interface OutputMessage extends Omit<Message, "role"> {
  role: string;
  metadata: unknown;
  sequence_number?: number;
}

function extractApprovalAction(
  message: OutputMessage,
): ChatApprovalActionCardData | null {
  const metadata =
    message.metadata && typeof message.metadata === "object"
      ? (message.metadata as Record<string, unknown>)
      : null;
  if (!metadata) return null;

  const direct = metadata.approval_action;
  if (direct && typeof direct === "object") {
    return direct as ChatApprovalActionCardData;
  }

  const nested = metadata.metadata;
  if (nested && typeof nested === "object") {
    const approvalAction = (nested as Record<string, unknown>).approval_action;
    if (approvalAction && typeof approvalAction === "object") {
      return approvalAction as ChatApprovalActionCardData;
    }
  }

  return null;
}

/**
 * Extended session carrying extra fields that the library type does not define
 * but our backend / window globals require.
 */
interface ExtendedSession extends IAgentScopeRuntimeWebUISession {
  /** Session identifier (channel:user_id format) */
  sessionId: string;
  /** User identifier */
  userId: string;
  /** Channel name */
  channel: string;
  /** Additional metadata */
  meta: Record<string, unknown>;
  /** Real backend UUID, used when id is overridden with a local timestamp. */
  realId?: string;
  /** Conversation status from backend. */
  status?: ChatStatus;
  /** ISO 8601 creation timestamp from backend. */
  createdAt?: string | null;
  /** Whether the backend is still generating a response for this session. */
  generating?: boolean;
}

// ---------------------------------------------------------------------------
// Message conversion helpers: backend flat messages → card-based UI format
// ---------------------------------------------------------------------------

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

/** Extract plain text from a message's content array. */
const extractTextFromContent = (content: unknown): string => {
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return String(content || "");
  return (content as ContentItem[])
    .filter((c) => c.type === "text")
    .map((c) => c.text || "")
    .filter(Boolean)
    .join("\n");
};

function resolveContentItemUrl(c: ContentItem): ContentItem {
  if (c.type === "image" && c.image_url) {
    return { ...c, image_url: toDisplayUrl(c.image_url as string) };
  }
  if (c.type === "audio" && c.data) {
    return { ...c, data: toDisplayUrl(c.data as string) };
  }
  if (c.type === "video" && c.video_url) {
    return { ...c, video_url: toDisplayUrl(c.video_url as string) };
  }
  if (c.type === "file" && (c.file_url || c.file_id)) {
    return {
      ...c,
      file_url: toDisplayUrl((c.file_url as string) || (c.file_id as string)),
      file_name: (c.filename as string) || (c.file_name as string) || "file",
    };
  }
  return c;
}

/** Map backend message content to request card content (text + image + file). */
function contentToRequestParts(
  content: unknown,
): Array<Record<string, unknown>> {
  if (typeof content === "string") {
    return [{ type: "text", text: content, status: "created" }];
  }
  if (!Array.isArray(content)) {
    return [{ type: "text", text: String(content || ""), status: "created" }];
  }
  const parts = (content as ContentItem[])
    .map(resolveContentItemUrl)
    .map((c) => ({ ...c, status: "created" }));

  if (parts.length === 0) {
    return [{ type: "text", text: "", status: "created" }];
  }

  return parts;
}
function normalizeOutputMessageContent(content: unknown): unknown {
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return content;
  return (content as ContentItem[]).map(resolveContentItemUrl);
}

/**
 * Convert a backend message to a response output message.
 * Maps system + plugin_call_output → role "tool" and strips metadata.
 */
const toOutputMessage = (msg: Message): OutputMessage => ({
  ...msg,
  role:
    msg.type === TYPE_PLUGIN_CALL_OUTPUT && msg.role === "system"
      ? ROLE_TOOL
      : msg.role,
  metadata: msg.metadata ?? null,
});

/** Build a user card (AgentScopeRuntimeRequestCard) from a user message. */
function buildUserCard(msg: Message): IAgentScopeRuntimeWebUIMessage {
  const contentParts = contentToRequestParts(msg.content);
  const timestamp = resolveMessageTimestamp({
    timestamp: msg.timestamp,
  });
  return {
    id: (msg.id as string) || generateId(),
    role: "user",
    cards: [
      {
        code: "AgentScopeRuntimeRequestCard",
        data: {
          input: [
            {
              role: "user",
              type: "message",
              content: contentParts,
            },
          ],
          headerMeta: {
            timestamp,
          },
        } as unknown as ChatRuntimeRequestCardData,
      },
    ],
  };
}

/**
 * Build an assistant response card (AgentScopeRuntimeResponseCard)
 * wrapping a group of consecutive non-user output messages.
 */
const buildResponseCard = (
  outputMessages: OutputMessage[],
): IAgentScopeRuntimeWebUIMessage => {
  const timestamp = resolveGroupTimestamp(
    outputMessages.map((message) => ({
      timestamp: message.timestamp,
    })),
  );
  const createdAt = timestamp ?? Date.now();
  const maxSeq = outputMessages.reduce(
    (max, m) => Math.max(max, m.sequence_number || 0),
    0,
  );

  const normalizedMessages = outputMessages.map((msg) => ({
    ...msg,
    content: normalizeOutputMessageContent(msg.content),
  }));

  const approvalAction =
    normalizedMessages.reduce<ChatApprovalActionCardData | null>(
      (found, message) => found ?? extractApprovalAction(message),
      null,
    );

  const cards: NonNullable<IAgentScopeRuntimeWebUIMessage["cards"]> = [
    {
      code: CARD_RESPONSE,
      data: {
        id: `response_${generateId()}`,
        output: normalizedMessages,
        object: "response",
        status: "completed",
        created_at: createdAt,
        sequence_number: maxSeq + 1,
        error: null,
        completed_at: createdAt,
        usage: null,
        headerMeta: {
          timestamp,
        },
      } as unknown as ChatRuntimeResponseCardData,
    },
  ];

  if (approvalAction) {
    cards.push({
      code: CARD_APPROVAL_ACTION,
      data: approvalAction,
    });
  }

  return {
    id: generateId(),
    role: ROLE_ASSISTANT,
    cards,
    msgStatus: "finished",
  };
};

/**
 * Convert flat backend messages into the card-based format expected by
 * the @agentscope-ai/chat component.
 *
 * - User messages → AgentScopeRuntimeRequestCard
 * - Consecutive non-user messages (assistant / system / tool) → grouped
 *   into a single AgentScopeRuntimeResponseCard with all output messages.
 */
export const convertMessages = (
  messages: Message[],
): IAgentScopeRuntimeWebUIMessage[] => {
  const result: IAgentScopeRuntimeWebUIMessage[] = [];
  let i = 0;

  while (i < messages.length) {
    if (messages[i].role === ROLE_USER) {
      result.push(buildUserCard(messages[i++]));
    } else {
      const outputMsgs: OutputMessage[] = [];
      while (i < messages.length && messages[i].role !== ROLE_USER) {
        outputMsgs.push(toOutputMessage(messages[i++]));
      }
      if (outputMsgs.length) result.push(buildResponseCard(outputMsgs));
    }
  }

  return result;
};

const chatSpecToSession = (chat: ChatSpec): ExtendedSession =>
  ({
    id: chat.id,
    name: chat.name || DEFAULT_SESSION_NAME,
    sessionId: chat.session_id,
    userId: chat.user_id,
    channel: chat.channel,
    messages: [],
    meta: chat.meta || {},
    status: chat.status ?? "idle",
    createdAt: chat.created_at ?? null,
  }) as ExtendedSession;

/** Returns true when id is a pure numeric local timestamp (not a backend UUID). */
const isLocalTimestamp = (id: string): boolean => /^\d+$/.test(id);

let lastLocalSessionTimestamp = 0;
let localSessionSequence = 0;

function createLocalSessionId(): string {
  const now = Date.now();
  if (now === lastLocalSessionTimestamp) {
    localSessionSequence += 1;
  } else {
    lastLocalSessionTimestamp = now;
    localSessionSequence = 0;
  }

  return `${now}${localSessionSequence.toString().padStart(3, "0")}`;
}

/** Detect if backend is still generating content for this chat. */
const isGenerating = (chatHistory: ChatHistory): boolean => {
  if (chatHistory.status === "running") return true;
  if (chatHistory.status === "idle") return false;
  const msgs = chatHistory.messages || [];
  if (msgs.length === 0) return false;
  const last = msgs[msgs.length - 1];
  return last.role === ROLE_USER;
};

const mergeGeneratingState = (
  backendStatus?: string,
  backendGenerating?: boolean,
  localGenerating?: boolean,
): boolean => {
  if (backendStatus === "running") return true;
  if (backendStatus === "idle") return false;
  if (typeof backendGenerating === "boolean") return backendGenerating;
  return Boolean(localGenerating);
};

/**
 * Resolve and persist the real backend UUID for a local timestamp session.
 * Stores the real UUID as realId while keeping the timestamp as id, so the
 * library's internal currentSessionId (timestamp) remains valid.
 * Returns the resolved real UUID, or null if not found.
 */
const mergeResolvedSession = (
  resolvedSession: ExtendedSession,
  localSession?: ExtendedSession,
  tempSessionId?: string,
): ExtendedSession => {
  const realId = resolvedSession.realId || resolvedSession.id;

  return {
    ...resolvedSession,
    id: localSession?.id || tempSessionId || resolvedSession.id,
    realId,
    sessionId: localSession?.sessionId || resolvedSession.sessionId,
    name: localSession?.name || resolvedSession.name,
    userId: localSession?.userId || resolvedSession.userId,
    channel: localSession?.channel || resolvedSession.channel,
    meta: localSession?.meta || resolvedSession.meta || {},
    createdAt: localSession?.createdAt || resolvedSession.createdAt,
    messages:
      resolvedSession.messages?.length > 0
        ? resolvedSession.messages
        : localSession?.messages || [],
    generating: mergeGeneratingState(
      resolvedSession.status,
      resolvedSession.generating,
      localSession?.generating,
    ),
  } as ExtendedSession;
};

const resolveRealId = (
  sessionList: IAgentScopeRuntimeWebUISession[],
  tempSessionId: string,
): { list: IAgentScopeRuntimeWebUISession[]; realId: string | null } => {
  const localSession = sessionList.find((s) => s.id === tempSessionId) as
    | ExtendedSession
    | undefined;
  const realSession = sessionList.find((s) => {
    const extendedSession = s as ExtendedSession;
    return (
      extendedSession.sessionId === tempSessionId &&
      (extendedSession.id !== tempSessionId || Boolean(extendedSession.realId))
    );
  });
  if (!realSession) return { list: sessionList, realId: null };

  const realUUID = (realSession as ExtendedSession).realId || realSession.id;
  const resolvedSession = mergeResolvedSession(
    realSession as ExtendedSession,
    localSession,
  );
  return {
    list: [
      resolvedSession,
      ...sessionList.filter((s) => s !== realSession && s !== localSession),
    ],
    realId: realUUID,
  };
};

const isPendingLocalSession = (
  session: IAgentScopeRuntimeWebUISession,
): session is ExtendedSession => {
  const extendedSession = session as ExtendedSession;
  return isLocalTimestamp(extendedSession.id) && !extendedSession.realId;
};

const mergePendingSession = (
  sessionList: IAgentScopeRuntimeWebUISession[],
  pendingSession: ExtendedSession,
): IAgentScopeRuntimeWebUISession[] => {
  return [
    pendingSession,
    ...sessionList.filter((session) => session.id !== pendingSession.id),
  ];
};

const mergePendingSessions = (
  sessionList: IAgentScopeRuntimeWebUISession[],
  pendingSessions: ExtendedSession[],
): IAgentScopeRuntimeWebUISession[] =>
  [...pendingSessions]
    .reverse()
    .reduce(
      (list, pendingSession) => mergePendingSession(list, pendingSession),
      sessionList,
    );

// ---------------------------------------------------------------------------
// Per-session user message persistence (survives page refresh)
// ---------------------------------------------------------------------------

const STORAGE_PREFIX = "copaw_pending_user_msg_";

function savePendingUserMessage(sessionId: string, text: string): void {
  try {
    sessionStorage.setItem(`${STORAGE_PREFIX}${sessionId}`, text);
  } catch {
    /* quota exceeded – ignore */
  }
}

function loadPendingUserMessage(sessionId: string): string {
  try {
    return sessionStorage.getItem(`${STORAGE_PREFIX}${sessionId}`) || "";
  } catch {
    return "";
  }
}

function loadPendingUserMessageFromCandidates(sessionIds: string[]): string {
  for (const sessionId of sessionIds) {
    const text = loadPendingUserMessage(sessionId);
    if (text) {
      return text;
    }
  }

  return "";
}

function clearPendingUserMessage(sessionId: string): void {
  try {
    sessionStorage.removeItem(`${STORAGE_PREFIX}${sessionId}`);
  } catch {
    /* ignore */
  }
}

// ---------------------------------------------------------------------------
// SessionApi
// ---------------------------------------------------------------------------

export class SessionApi implements IAgentScopeRuntimeWebUISessionAPI {
  private sessionList: IAgentScopeRuntimeWebUISession[] = [];
  private intendedSessionId: string | null = null;

  /**
   * When set, getSessionList will move the matching session to the front on the first call,
   * so the library's useMount auto-selects it instead of always defaulting to sessions[0].
   * Cleared after first use.
   */
  preferredChatId: string | null = null;

  /**
   * Cache the latest user message for a chat so it can be patched into
   * history during reconnect (the backend only persists it after generation
   * completes). Persisted to sessionStorage so it survives page refresh.
   */
  setLastUserMessage(sessionId: string, text: string): void {
    if (!sessionId || !text) return;
    savePendingUserMessage(sessionId, text);
  }

  /**
   * Deduplicates concurrent getSessionList calls so that two parallel
   * invocations share one network request and write sessionList only once,
   * preserving any realId mappings that were already resolved.
   */
  private sessionListRequest: Promise<IAgentScopeRuntimeWebUISession[]> | null =
    null;

  /**
   * Deduplicates concurrent getSession calls for the same sessionId.
   * Key: sessionId, Value: in-flight promise for getSession.
   */
  private sessionRequests: Map<
    string,
    Promise<IAgentScopeRuntimeWebUISession>
  > = new Map();

  /**
   * Called when a temporary timestamp session id is resolved to a real backend
   * UUID. Consumers (e.g. Chat/index.tsx) can register here to update the URL.
   */
  onSessionIdResolved: ((tempId: string, realId: string) => void) | null = null;

  /**
   * Called after a session is removed. Consumers can register here to clear
   * the session id from the URL.
   */
  onSessionRemoved: ((removedId: string) => void) | null = null;

  /**
   * Called when a session is selected from the session list.
   * Consumers can register here to update the URL when switching sessions.
   */
  onSessionSelected:
    | ((sessionId: string | null | undefined, realId: string | null) => void)
    | null = null;

  /**
   * Called when a new session is created.
   * Consumers can register here to update the URL with the new session id.
   */
  onSessionCreated: ((sessionId: string) => void) | null = null;

  /**
   * When reconnecting to a running conversation, the backend history may not
   * include the latest user message (it's only persisted after generation
   * completes). If generating, look up the cached text from sessionStorage
   * and patch it into the message list.
   *
   * When not generating the conversation is done — clear the cached entry.
   */
  private patchLastUserMessage(
    messages: IAgentScopeRuntimeWebUIMessage[],
    generating: boolean,
    backendSessionId: string,
    fallbackSessionIds: string[] = [],
  ): void {
    const candidateSessionIds = Array.from(
      new Set([backendSessionId, ...fallbackSessionIds].filter(Boolean)),
    );

    if (!generating) {
      candidateSessionIds.forEach(clearPendingUserMessage);
      return;
    }

    const cachedText =
      loadPendingUserMessageFromCandidates(candidateSessionIds);
    if (!cachedText) return;

    const lastMsg = messages[messages.length - 1];
    if (lastMsg?.role === ROLE_USER) {
      const text = extractTextFromContent(
        lastMsg?.cards?.[0]?.data?.input?.[0]?.content,
      );
      if (!text) {
        lastMsg.cards = buildUserCard({
          content: [{ type: "text", text: cachedText }],
          role: ROLE_USER,
        } as Message).cards;
      }
    } else {
      messages.push(
        buildUserCard({
          content: [{ type: "text", text: cachedText }],
          role: ROLE_USER,
        } as Message),
      );
    }
  }

  private createEmptySession(sessionId: string): ExtendedSession {
    window.currentSessionId = sessionId;
    // ==================== userId 统一整改 (Kun He) ====================
    // 使用 getUserId() 获取用户 ID，优先级：iframe > window > default
    window.currentUserId = getUserId();
    window.currentChannel = getChannel();
    // ==================== userId 统一整改结束 ====================
    return {
      id: sessionId,
      name: DEFAULT_SESSION_NAME,
      sessionId,
      userId: getUserId(),
      channel: getChannel(),
      messages: [],
      meta: {},
    } as ExtendedSession;
  }

  private updateWindowVariables(session: ExtendedSession): void {
    window.currentSessionId = session.sessionId || "";
    // ==================== userId 统一整改 (Kun He) ====================
    // 使用 getUserId() 获取用户 ID，传入 session.userId 作为候选值
    window.currentUserId = getUserIdWithoutWindow(session.userId);
    window.currentChannel = getChannelWithoutWindow(session.channel);
    // ==================== userId 统一整改结束 ====================
  }

  private getLocalSession(sessionId: string): IAgentScopeRuntimeWebUISession {
    const local = this.sessionList.find((s) => s.id === sessionId);
    if (local) {
      this.updateWindowVariables(local as ExtendedSession);
      return local;
    }
    return this.createEmptySession(sessionId);
  }

  private findSessionByIdentity(
    sessionId: string,
  ): ExtendedSession | undefined {
    return this.sessionList.find((session) => {
      const extendedSession = session as ExtendedSession;
      return (
        extendedSession.id === sessionId || extendedSession.realId === sessionId
      );
    }) as ExtendedSession | undefined;
  }

  private getPendingSessions(): ExtendedSession[] {
    return this.sessionList.filter(isPendingLocalSession) as ExtendedSession[];
  }

  private getLatestPendingSession(): ExtendedSession | null {
    return this.getPendingSessions()[0] ?? null;
  }

  private isActivePendingSession(
    pendingSessionId: string,
    logicalSessionId: string = pendingSessionId,
  ): boolean {
    const currentSessionId = window.currentSessionId;
    if (!currentSessionId) {
      return this.getLatestPendingSession()?.id === pendingSessionId;
    }

    return (
      currentSessionId === pendingSessionId ||
      currentSessionId === logicalSessionId
    );
  }

  private notifyResolvedSessionIfActive(
    pendingSessionId: string,
    realId: string,
    logicalSessionId: string = pendingSessionId,
  ): void {
    if (this.isActivePendingSession(pendingSessionId, logicalSessionId)) {
      this.onSessionIdResolved?.(pendingSessionId, realId);
    }
  }

  getLogicalSessionId(sessionId: string): string {
    if (!sessionId) {
      return "";
    }

    const session = this.findSessionByIdentity(sessionId);
    return session?.sessionId || sessionId;
  }

  /**
   * Returns the real backend UUID for a session identified by id (which may be
   * a local timestamp). Returns null when not yet resolved or not found.
   */
  getRealIdForSession(sessionId: string): string | null {
    return (
      this.findSessionByIdentity(sessionId)?.realId ??
      getResolvedChatId(sessionId)
    );
  }

  getChatIdForSession(sessionId: string): string | null {
    if (!sessionId) {
      return null;
    }

    const session = this.findSessionByIdentity(sessionId);
    if (session?.realId) {
      return session.realId;
    }

    if (session && !isLocalTimestamp(session.id)) {
      return session.id;
    }

    if (isLocalTimestamp(sessionId)) {
      const resolvedChatId = getResolvedChatId(sessionId);
      if (resolvedChatId) {
        return resolvedChatId;
      }

      const matches = this.sessionList.filter(
        (session) => (session as ExtendedSession).sessionId === sessionId,
      ) as ExtendedSession[];
      if (matches.length === 1) {
        return matches[0].realId || matches[0].id;
      }

      return null;
    }

    const matchesLogicalSessionId = this.sessionList.some(
      (session) => (session as ExtendedSession).sessionId === sessionId,
    );
    if (matchesLogicalSessionId) {
      return null;
    }

    return sessionId;
  }

  /**
   * 获取当前的临时会话ID（用于发送消息时作为 session_id）
   */
  getPendingSessionId(): string | null {
    return this.getLatestPendingSession()?.id ?? null;
  }

  /**
   * 清除临时会话（消息发送完成后调用）
   */
  clearPendingSession(): void {
    return;
  }

  /**
   * 消息发送完成后，创建真实会话记录并更新URL
   * @param realId 后端返回的真实UUID
   * @param name 会话名称（可选，默认使用临时会话的名称）
   */
  async createSessionFromPending(realId: string, name?: string): Promise<void> {
    const pendingSession = this.getLatestPendingSession();
    if (!pendingSession) return;

    const pendingSessionId = pendingSession.id;
    const session: ExtendedSession = {
      id: realId,
      sessionId: pendingSession.sessionId,
      userId: pendingSession.userId,
      channel: pendingSession.channel,
      name: name || pendingSession.name || DEFAULT_SESSION_NAME,
      messages: [],
      meta: pendingSession.meta || {},
      createdAt: pendingSession.createdAt,
    };

    // 添加到历史列表
    this.sessionList = [
      session,
      ...this.sessionList.filter((item) => item.id !== pendingSessionId),
    ];

    // 触发回调更新URL
    rememberResolvedChatId(pendingSession.id, realId);
    this.notifyResolvedSessionIfActive(
      pendingSession.id,
      realId,
      pendingSession.sessionId,
    );

    // 更新 window 变量
    this.updateWindowVariables(session);
  }

  async getSessionList() {
    if (this.sessionListRequest) return this.sessionListRequest;

    this.sessionListRequest = (async () => {
      try {
        const allowPreferredSelection = this.sessionList.length === 0;
        const pendingSessions = this.getPendingSessions();

        const [chats, jobsResult] = await Promise.all([
          api.listChats(),
          cronJobApi.listCronJobs().catch(() => null),
        ]);
        const activeTaskJobIds: ReadonlySet<string> | null =
          jobsResult === null
            ? null
            : new Set<string>(
                jobsResult
                  .filter((job) => job.task_type === "agent")
                  .map((job) => String(job.id)),
              );
        const newList = chats
          .filter((c) => c.id && c.id !== "undefined" && c.id !== "null")
          .map(chatSpecToSession)
          .reverse();
        const filteredList = filterStaleTaskSessions(newList, activeTaskJobIds);

        const resolvedPendingSessionIds = new Set<string>();
        pendingSessions.forEach((pendingSession) => {
          const matchedIndex = filteredList.findIndex(
            (session) =>
              (session as ExtendedSession).sessionId ===
              pendingSession.sessionId,
          );
          if (matchedIndex === -1) {
            return;
          }

          const matchedBackendSession = filteredList[
            matchedIndex
          ] as ExtendedSession;
          const realId = matchedBackendSession.id;
          filteredList[matchedIndex] = mergeResolvedSession(
            matchedBackendSession,
            pendingSession,
            pendingSession.id,
          );
          resolvedPendingSessionIds.add(pendingSession.id);
          rememberResolvedChatId(pendingSession.id, realId);
          this.notifyResolvedSessionIfActive(
            pendingSession.id,
            realId,
            pendingSession.sessionId,
          );

          if (
            window.currentSessionId === pendingSession.id ||
            window.currentSessionId === pendingSession.sessionId
          ) {
            window.currentSessionId =
              matchedBackendSession.sessionId || pendingSession.id;
          }
        });

        const previousResolvedSessions = this.sessionList.filter((session) => {
          const extendedSession = session as ExtendedSession;
          return (
            isLocalTimestamp(extendedSession.id) &&
            Boolean(extendedSession.realId)
          );
        }) as ExtendedSession[];

        previousResolvedSessions.forEach((localResolvedSession) => {
          const matchedIndex = filteredList.findIndex(
            (session) => session.id === localResolvedSession.realId,
          );
          if (matchedIndex > -1) {
            const backendSession = filteredList[
              matchedIndex
            ] as ExtendedSession;
            filteredList[matchedIndex] = {
              ...backendSession,
              id: localResolvedSession.id,
              realId: localResolvedSession.realId,
              sessionId:
                localResolvedSession.sessionId || backendSession.sessionId,
              name: localResolvedSession.name || backendSession.name,
              userId: localResolvedSession.userId || backendSession.userId,
              channel: localResolvedSession.channel || backendSession.channel,
              meta: localResolvedSession.meta || backendSession.meta || {},
              createdAt:
                localResolvedSession.createdAt || backendSession.createdAt,
              messages:
                backendSession.messages?.length > 0
                  ? backendSession.messages
                  : localResolvedSession.messages || [],
              generating: mergeGeneratingState(
                backendSession.status,
                backendSession.generating,
                localResolvedSession.generating,
              ),
            } as ExtendedSession;
          }
        });

        // 合并后端会话列表
        this.sessionList = mergePendingSessions(
          filteredList,
          pendingSessions.filter(
            (pendingSession) =>
              !resolvedPendingSessionIds.has(pendingSession.id),
          ),
        );

        this.sessionList = applyPreferredSessionSelection({
          sessions: this.sessionList,
          preferredChatId: this.preferredChatId,
          allowReorder: allowPreferredSelection,
        });
        this.preferredChatId = null;

        return [...this.sessionList];
      } finally {
        this.sessionListRequest = null;
      }
    })();

    return this.sessionListRequest;
  }

  /** Track the last session ID that triggered onSessionSelected to avoid duplicate calls. */
  private lastSelectedSessionId: string | null = null;

  setSelectedSessionIntent(sessionId: string | undefined | null): void {
    this.intendedSessionId = sessionId ?? null;
  }

  async getSession(sessionId: string) {
    const existingRequest = this.sessionRequests.get(sessionId);
    if (existingRequest) return existingRequest;

    const requestPromise = this._doGetSession(sessionId);
    this.sessionRequests.set(sessionId, requestPromise);

    try {
      const session = await requestPromise;
      // Trigger onSessionSelected only when session actually changes
      if (
        shouldNotifySessionSelected({
          requestedSessionId: sessionId,
          intendedSessionId: this.intendedSessionId,
        }) &&
        sessionId !== this.lastSelectedSessionId
      ) {
        this.lastSelectedSessionId = sessionId;
        const extendedSession = session as ExtendedSession;
        const realId = extendedSession.realId || null;
        this.onSessionSelected?.(sessionId, realId);
      }
      return session;
    } finally {
      this.sessionRequests.delete(sessionId);
    }
  }

  private async getResolvedLocalTimestampSession(
    sessionId: string,
    fromList: ExtendedSession,
  ): Promise<ExtendedSession> {
    const realId = fromList.realId;
    if (!realId) {
      return this.getLocalSession(sessionId) as ExtendedSession;
    }

    const chatHistory = await api.getChat(realId);
    const backendGenerating = isGenerating(chatHistory);
    const backendMessages = convertMessages(chatHistory.messages || []);
    const messages =
      backendMessages.length > 0 ? backendMessages : fromList.messages || [];
    const generating = mergeGeneratingState(
      chatHistory.status,
      backendGenerating,
      fromList.generating,
    );
    this.patchLastUserMessage(messages, generating, realId, [
      sessionId,
      fromList.sessionId,
    ]);
    const session: ExtendedSession = {
      id: sessionId,
      name: fromList.name || DEFAULT_SESSION_NAME,
      sessionId: fromList.sessionId || sessionId,
      // ==================== userId 统一整改 (Kun He) ====================
      userId: getUserIdWithoutWindow(fromList.userId),
      channel: getChannelWithoutWindow(fromList.channel),
      // ==================== userId 统一整改结束 ====================
      messages,
      meta: fromList.meta || {},
      realId,
      generating,
    };
    this.updateWindowVariables(session);
    return session;
  }

  private async _doGetSession(
    sessionId: string,
  ): Promise<IAgentScopeRuntimeWebUISession> {
    // --- Local timestamp ID (New Chat before first reply) ---
    if (isLocalTimestamp(sessionId)) {
      let fromList = this.sessionList.find((s) => s.id === sessionId) as
        | ExtendedSession
        | undefined;

      // If realId is already resolved, use it directly to fetch history.
      if (fromList?.realId) {
        return this.getResolvedLocalTimestampSession(sessionId, fromList);
      }

      // The stream may already have created a backend chat while this tab still
      // only knows the local timestamp id. Refresh once so switching back to a
      // running local session can resolve its backend status before reconnecting.
      if (!fromList?.realId) {
        await this.getSessionList();
        fromList = this.sessionList.find((s) => s.id === sessionId) as
          | ExtendedSession
          | undefined;

        if (fromList?.realId) {
          return this.getResolvedLocalTimestampSession(sessionId, fromList);
        }

        return this.getLocalSession(sessionId);
      }
    }

    // --- No session selected (e.g. after delete) ---
    if (!sessionId || sessionId === "undefined" || sessionId === "null") {
      return this.createEmptySession(createLocalSessionId());
    }

    // --- Regular backend UUID ---
    const fromList = this.sessionList.find((s) => s.id === sessionId) as
      | ExtendedSession
      | undefined;

    const chatHistory = await api.getChat(sessionId);
    const generating = isGenerating(chatHistory);
    const messages = convertMessages(chatHistory.messages || []);
    this.patchLastUserMessage(messages, generating, sessionId, [
      fromList?.sessionId,
      fromList?.realId,
    ]);
    const session: ExtendedSession = {
      id: sessionId,
      name: fromList?.name || sessionId,
      sessionId: fromList?.sessionId || sessionId,
      // ==================== userId 统一整改 (Kun He) ====================
      userId: getUserIdWithoutWindow(fromList?.userId),
      channel: getChannelWithoutWindow(fromList?.channel),
      // ==================== userId 统一整改结束 ====================
      messages,
      meta: fromList?.meta || {},
      generating,
    };

    this.updateWindowVariables(session);
    return session;
  }

  async updateSession(session: Partial<IAgentScopeRuntimeWebUISession>) {
    const shouldKeepLocalMessages = Boolean(
      session.id &&
        isLocalTimestamp(session.id) &&
        !this.getRealIdForSession(session.id),
    );
    const nextSession = {
      ...session,
      messages: shouldKeepLocalMessages ? session.messages || [] : [],
    };
    const index = this.sessionList.findIndex((s) => s.id === nextSession.id);

    if (index > -1) {
      this.sessionList[index] = { ...this.sessionList[index], ...nextSession };

      const existing = this.sessionList[index] as ExtendedSession;
      if (isLocalTimestamp(existing.id) && !existing.realId) {
        const tempId = existing.id;
        await this.getSessionList().then(() => {
          const { list, realId } = resolveRealId(this.sessionList, tempId);
          if (realId) {
            this.sessionList = list;
            rememberResolvedChatId(tempId, realId);
            this.notifyResolvedSessionIfActive(tempId, realId);
          }
        });
      } else {
        const tempId = nextSession.id!;
        await this.getSessionList().then(() => {
          const { list, realId } = resolveRealId(this.sessionList, tempId);
          this.sessionList = list;
          if (realId) {
            rememberResolvedChatId(tempId, realId);
            this.notifyResolvedSessionIfActive(tempId, realId);
          }
        });
      }
    } else {
      if (shouldKeepLocalMessages) {
        this.sessionList = mergePendingSession(
          this.sessionList,
          nextSession as ExtendedSession,
        );
      }

      const tempId = nextSession.id!;
      await this.getSessionList().then(() => {
        const { list, realId } = resolveRealId(this.sessionList, tempId);
        this.sessionList = list;
        if (realId) {
          rememberResolvedChatId(tempId, realId);
          this.notifyResolvedSessionIfActive(tempId, realId);
        }
      });
    }

    return [...this.sessionList];
  }

  async createSession(session: Partial<IAgentScopeRuntimeWebUISession>) {
    // 生成临时时间戳ID（只在内存中使用，不添加到历史列表）
    session.id = createLocalSessionId();

    // ==================== userId 统一整改 (Kun He) ====================
    // 使用 getUserId() 获取用户 ID
    const extended: ExtendedSession = {
      ...session,
      sessionId: session.id,
      userId: getUserId(),
      channel: getChannel(),
      createdAt: new Date().toISOString(),
      name: session.name || DEFAULT_SESSION_NAME,
      messages: [],
      meta: {},
    } as ExtendedSession;
    // ==================== userId 统一整改结束 ====================

    // 等消息发送完成后，后端返回真实UUID时才创建历史记录
    this.updateWindowVariables(extended);

    this.sessionList = mergePendingSession(this.sessionList, extended);

    // 触发回调（URL 清空，不导航到临时ID）
    this.onSessionCreated?.(session.id);

    // 返回当前列表（不包含临时会话）
    return [...this.sessionList];
  }

  async removeSession(session: Partial<IAgentScopeRuntimeWebUISession>) {
    if (!session.id) return [...this.sessionList];

    const { id: sessionId } = session;

    const existing = this.sessionList.find((s) => s.id === sessionId) as
      | ExtendedSession
      | undefined;

    const deleteId =
      this.getChatIdForSession(sessionId) ??
      (isLocalTimestamp(sessionId) ? null : sessionId);

    if (deleteId) await api.deleteChat(deleteId);

    this.sessionList = this.sessionList.filter((s) => s.id !== sessionId);

    const resolvedId = existing?.realId ?? sessionId;
    forgetResolvedChatId(sessionId);
    if (deleteId) {
      forgetResolvedChatIdsForChat(deleteId);
    }
    this.onSessionRemoved?.(resolvedId);

    return [...this.sessionList];
  }
}

export default new SessionApi();
