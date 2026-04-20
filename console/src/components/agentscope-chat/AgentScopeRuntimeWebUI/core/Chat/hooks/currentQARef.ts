import type { IAgentScopeRuntimeWebUIMessage } from "@/components/agentscope-chat";

export type LiveResponseMessage = IAgentScopeRuntimeWebUIMessage & {
  liveHeaderTimestamp?: number;
};

export type CurrentQARef = React.MutableRefObject<{
  request?: IAgentScopeRuntimeWebUIMessage;
  response?: LiveResponseMessage;
  abortController?: AbortController;
}>;
