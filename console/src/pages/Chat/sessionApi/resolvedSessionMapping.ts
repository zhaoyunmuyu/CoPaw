import type { IAgentScopeRuntimeWebUISession } from "@/components/agentscope-chat";

const STORAGE_KEY = "copaw_resolved_chat_ids";

type ResolvedSessionMapping = Record<string, string>;
type SessionWithIdentity = IAgentScopeRuntimeWebUISession & {
  sessionId?: string;
  createdAt?: string | null;
};

function readResolvedSessionMapping(): ResolvedSessionMapping {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return {};
    }

    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function writeResolvedSessionMapping(
  mapping: ResolvedSessionMapping,
): void {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(mapping));
  } catch {
    // Ignore storage failures. The runtime can still function in-memory.
  }
}

export function rememberResolvedChatId(
  temporarySessionId: string,
  chatId: string,
): void {
  if (!temporarySessionId || !chatId) {
    return;
  }

  writeResolvedSessionMapping({
    ...readResolvedSessionMapping(),
    [temporarySessionId]: chatId,
  });
}

export function forgetResolvedChatId(temporarySessionId: string): void {
  if (!temporarySessionId) {
    return;
  }

  const mapping = readResolvedSessionMapping();
  if (!(temporarySessionId in mapping)) {
    return;
  }

  delete mapping[temporarySessionId];
  writeResolvedSessionMapping(mapping);
}

export function forgetResolvedChatIdsForChat(chatId: string): void {
  if (!chatId) {
    return;
  }

  const mapping = readResolvedSessionMapping();
  let changed = false;

  Object.entries(mapping).forEach(([temporarySessionId, resolvedChatId]) => {
    if (temporarySessionId === chatId || resolvedChatId === chatId) {
      delete mapping[temporarySessionId];
      changed = true;
    }
  });

  if (changed) {
    writeResolvedSessionMapping(mapping);
  }
}

export function getResolvedChatId(
  temporarySessionId: string | undefined | null,
): string | null {
  if (!temporarySessionId) {
    return null;
  }

  return readResolvedSessionMapping()[temporarySessionId] ?? null;
}

function getSessionCreatedAt(session: IAgentScopeRuntimeWebUISession): number {
  const createdAt = (session as SessionWithIdentity).createdAt;
  if (!createdAt) {
    return 0;
  }

  const timestamp = Date.parse(createdAt);
  return Number.isNaN(timestamp) ? 0 : timestamp;
}

function resolveLogicalSessionDeepLink(options: {
  requestedSessionId: string;
  sessionList: IAgentScopeRuntimeWebUISession[];
}): string | null {
  const { requestedSessionId, sessionList } = options;
  const matches = sessionList.filter(
    (session) =>
      (session as SessionWithIdentity).sessionId === requestedSessionId,
  );

  if (matches.length === 0) {
    return null;
  }

  return [...matches].sort(
    (left, right) => getSessionCreatedAt(right) - getSessionCreatedAt(left),
  )[0].id;
}

export function resolveRequestedSessionId(options: {
  requestedSessionId: string | undefined;
  sessionList: IAgentScopeRuntimeWebUISession[];
}): string | undefined {
  const { requestedSessionId, sessionList } = options;
  if (!requestedSessionId) {
    return undefined;
  }

  if (sessionList.some((session) => session.id === requestedSessionId)) {
    return requestedSessionId;
  }

  const resolvedChatId = getResolvedChatId(requestedSessionId);
  if (!resolvedChatId) {
    return (
      resolveLogicalSessionDeepLink({
        requestedSessionId,
        sessionList,
      }) ?? requestedSessionId
    );
  }

  if (sessionList.some((session) => session.id === resolvedChatId)) {
    return resolvedChatId;
  }

  forgetResolvedChatId(requestedSessionId);

  return (
    resolveLogicalSessionDeepLink({
      requestedSessionId,
      sessionList,
    }) ?? undefined
  );
}

export function matchesResolvedChatId(options: {
  requestedSessionId: string | undefined | null;
  chatId: string | null;
}): boolean {
  const { requestedSessionId, chatId } = options;
  if (!requestedSessionId || !chatId) {
    return false;
  }

  return getResolvedChatId(requestedSessionId) === chatId;
}
