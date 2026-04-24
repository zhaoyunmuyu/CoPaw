import type { IAgentScopeRuntimeWebUISession } from "@/components/agentscope-chat";
import { resolveRequestedSessionId } from "./resolvedSessionMapping";

interface GetInitialSessionIdOptions {
  pathname: string;
  sessionList: IAgentScopeRuntimeWebUISession[];
}

interface InitialSessionSelection {
  requestedSessionId?: string;
  resolvedSessionId?: string;
}

export function getInitialSessionSelection({
  pathname,
  sessionList,
}: GetInitialSessionIdOptions): InitialSessionSelection {
  const match = pathname.match(/^\/chat\/(.+)$/);
  if (!match?.[1]) {
    return {};
  }

  const requestedSessionId = match[1];
  return {
    requestedSessionId,
    resolvedSessionId: resolveRequestedSessionId({
      requestedSessionId,
      sessionList,
    }),
  };
}

export function getInitialSessionId({
  pathname,
  sessionList,
}: GetInitialSessionIdOptions): string | undefined {
  return getInitialSessionSelection({
    pathname,
    sessionList,
  }).resolvedSessionId;
}
