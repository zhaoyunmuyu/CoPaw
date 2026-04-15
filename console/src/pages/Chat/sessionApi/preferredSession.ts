interface SessionLike {
  id?: string;
}

interface ApplyPreferredSessionSelectionOptions<T extends SessionLike> {
  sessions: T[];
  preferredChatId: string | null;
  allowReorder: boolean;
}

export function applyPreferredSessionSelection<T extends SessionLike>({
  sessions,
  preferredChatId,
  allowReorder,
}: ApplyPreferredSessionSelectionOptions<T>): T[] {
  if (!preferredChatId || !allowReorder) {
    return [...sessions];
  }

  const preferredIndex = sessions.findIndex(
    (session) => session.id === preferredChatId,
  );

  if (preferredIndex <= 0) {
    return [...sessions];
  }

  const nextSessions = [...sessions];
  const [preferredSession] = nextSessions.splice(preferredIndex, 1);
  nextSessions.unshift(preferredSession);
  return nextSessions;
}
