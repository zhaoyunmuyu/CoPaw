interface SessionLike {
  id?: string;
  meta?: Record<string, unknown> | null;
}

export function filterStaleTaskSessions<T extends SessionLike>(
  sessions: T[],
  activeTaskJobIds: ReadonlySet<string> | null,
): T[] {
  if (activeTaskJobIds === null) {
    return [...sessions];
  }

  return sessions.filter((session) => {
    const meta = session.meta ?? {};
    if (meta.session_kind !== "task") {
      return true;
    }

    const taskJobId = String(meta.task_job_id ?? "").trim();
    return Boolean(taskJobId) && activeTaskJobIds.has(taskJobId);
  });
}
