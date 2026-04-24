import React, { useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
// ==================== 组件引入方式变更 (Kun He) ====================
import { useChatAnywhereSessionsState } from "@/components/agentscope-chat";
// ==================== 组件引入方式变更结束 ====================
import { useAgentStore } from "@/stores/agentStore";
import { getInitialSessionSelection } from "../../sessionApi/initialSessionSelection";
import { getSessionAgentId } from "../../sessionApi/sessionAgent";

/**
 * URL chatId → context currentSessionId (one direction of bidirectional sync).
 *
 * Only reacts to URL or session list changes. currentSessionId is read via ref
 * to avoid triggering the effect when the context changes from the other direction
 * (context → URL via onSessionSelected), which would cause circular re-loads.
 */
const ChatSessionInitializer: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();

  const { sessions, currentSessionId, setCurrentSessionId } =
    useChatAnywhereSessionsState();
  const { selectedAgent, setSelectedAgent } = useAgentStore();

  const currentSessionIdRef = useRef(currentSessionId);
  currentSessionIdRef.current = currentSessionId;

  useEffect(() => {
    if (!sessions.length) return;

    const { requestedSessionId, resolvedSessionId } = getInitialSessionSelection({
      pathname: location.pathname,
      sessionList: sessions,
    });

    if (!resolvedSessionId) return;

    const matching = sessions.find((s) => s.id === resolvedSessionId);
    if (matching && currentSessionIdRef.current !== matching.id) {
      const sessionAgentId = getSessionAgentId(
        (matching as { meta?: Record<string, unknown> | null }).meta,
      );
      if (sessionAgentId && sessionAgentId !== selectedAgent) {
        setSelectedAgent(sessionAgentId);
      }
      setCurrentSessionId(matching.id);
    }

    if (
      requestedSessionId &&
      resolvedSessionId !== requestedSessionId
    ) {
      navigate(`/chat/${resolvedSessionId}`, { replace: true });
    }
    // Intentionally exclude currentSessionId from deps: only react to URL / session list changes.
    // currentSessionId is read via ref to avoid circular triggers.
  }, [
    location.pathname,
    navigate,
    selectedAgent,
    sessions,
    setCurrentSessionId,
    setSelectedAgent,
  ]);

  return null;
};

export default ChatSessionInitializer;
