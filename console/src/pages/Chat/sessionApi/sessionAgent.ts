export function getSessionAgentId(
  meta: Record<string, unknown> | null | undefined,
): string | null {
  const agentId = String(meta?.agent_id ?? "").trim();
  return agentId || null;
}
