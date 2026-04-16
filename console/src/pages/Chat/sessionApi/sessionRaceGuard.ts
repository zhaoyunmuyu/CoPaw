interface SessionLoadResultOptions {
  requestedSessionId: string | undefined;
  currentSessionId: string | undefined;
}

interface SessionSelectedNotificationOptions {
  requestedSessionId: string;
  intendedSessionId: string | null;
}

export function shouldApplySessionLoadResult({
  requestedSessionId,
  currentSessionId,
}: SessionLoadResultOptions): boolean {
  return Boolean(requestedSessionId) && requestedSessionId === currentSessionId;
}

export function shouldNotifySessionSelected({
  requestedSessionId,
  intendedSessionId,
}: SessionSelectedNotificationOptions): boolean {
  if (!intendedSessionId) {
    return true;
  }

  return requestedSessionId === intendedSessionId;
}
