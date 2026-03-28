import { AgentScopeRuntimeRunStatus, IAgentScopeRuntimeMessage, ITextContent } from "../types";
import { Thinking } from "@/chat";

export default function Reasoning({ data, loading }: { data: IAgentScopeRuntimeMessage; loading?: boolean }) {

  if (data.status === AgentScopeRuntimeRunStatus.Created) return null;

  const content = data?.content?.[0] as ITextContent;
  if (!content) return null;

  return <Thinking
    loading={loading ?? data.status === AgentScopeRuntimeRunStatus.InProgress}
    title="Thinking"
    content={content.text}

  ></Thinking>;
}
