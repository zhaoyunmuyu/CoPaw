import { IAgentScopeRuntimeWebUIMessage } from "@/components/agentscope-chat";

export interface IAgentScopeRuntimeWebUISession {
  /**
   * @description 会话的唯一标识符
   * @descriptionEn Unique identifier for the session
   */
  id: string;
  /**
   * @description 会话的名称
   * @descriptionEn Name of the session
   */
  name: string;
  /**
   * @description 会话的消息列表
   * @descriptionEn Message list for the session
   */
  messages: IAgentScopeRuntimeWebUIMessage[];
  /**
   * @description 对话是否仍在生成中（后端未完成），用于触发 SSE 重连
   * @descriptionEn Whether the conversation is still generating (backend not finished), used to trigger SSE reconnection
   */
  generating?: boolean;
}

export interface IAgentScopeRuntimeWebUISessionsContext {
  sessions: IAgentScopeRuntimeWebUISession[];
  setSessions: (sessions: IAgentScopeRuntimeWebUISession[]) => void;
  getSessions: () => IAgentScopeRuntimeWebUISession[];
  currentSessionId: string | undefined;
  setCurrentSessionId: (sessionId: string | undefined) => void;
  getCurrentSessionId: () => string | undefined;
  // 会话加载状态，用于在切换会话时保持显示旧消息，避免闪现欢迎页
  isSessionLoading: boolean;
  setSessionLoading: (loading: boolean) => void;
  // 会话列表加载状态，用于首次加载时显示骨架屏
  isSessionsListLoading: boolean;
  setSessionsListLoading: (loading: boolean) => void;
}
