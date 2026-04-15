import { createContext, useContextSelector } from "use-context-selector";
import { IAgentScopeRuntimeWebUISessionsContext } from "../types/ISessions";
import { IAgentScopeRuntimeWebUISessionAPI } from "../types";
import { useGetState, useMount } from "ahooks";
import { IAgentScopeRuntimeWebUISession } from "../types/ISessions";
import React, { useEffect } from "react";
import { ChatAnywhereMessagesContext } from "./ChatAnywhereMessagesContext";
import { useChatAnywhereOptions } from "./ChatAnywhereOptionsContext";
import ReactDOM from "react-dom";
import { useAsyncEffect } from "ahooks";
import { emit } from "./useChatAnywhereEventEmitter";
import { shouldApplySessionLoadResult } from "@/pages/Chat/sessionApi/sessionRaceGuard";

interface SessionApiWithIntent {
  setSelectedSessionIntent?: (sessionId: string | undefined | null) => void;
}

interface SessionOptions {
  api?: IAgentScopeRuntimeWebUISessionAPI & SessionApiWithIntent;
}

interface LoadSessionMessagesOptions {
  requestedSessionId: string | undefined;
  clearBeforeLoad: boolean;
  options: SessionOptions;
  setMessages: (messages: any) => void;
  getCurrentSessionId: () => string | undefined;
}

async function loadSessionMessages({
  requestedSessionId,
  clearBeforeLoad,
  options,
  setMessages,
  getCurrentSessionId,
}: LoadSessionMessagesOptions): Promise<boolean> {
  if (!requestedSessionId || !options.api) {
    if (clearBeforeLoad) {
      ReactDOM.flushSync(() => {
        setMessages([]);
      });
    }
    return false;
  }

  const sessionApi = options.api as SessionApiWithIntent | undefined;
  sessionApi?.setSelectedSessionIntent?.(requestedSessionId);

  if (clearBeforeLoad) {
    ReactDOM.flushSync(() => {
      setMessages([]);
    });
  }

  const session = await options.api.getSession(requestedSessionId);
  if (
    !shouldApplySessionLoadResult({
      requestedSessionId,
      currentSessionId: getCurrentSessionId(),
    })
  ) {
    return false;
  }

  const messages = session?.messages || [];
  setMessages(
    messages.map((item) => {
      return {
        ...item,
        history: true,
      };
    }),
  );

  if (session?.generating) {
    emit({ type: "handleReconnect", data: { session_id: requestedSessionId } });
  }

  return true;
}

export const ChatAnywhereSessionsContext =
  createContext<IAgentScopeRuntimeWebUISessionsContext>({
    sessions: [],
    setSessions: () => {},
    getSessions: () => [],
    currentSessionId: undefined,
    setCurrentSessionId: () => {},
    getCurrentSessionId: () => "",
  });

export function ChatAnywhereSessionsContextProvider(props: {
  children: React.ReactNode | React.ReactNode[];
}) {
  const options = useChatAnywhereOptions((v) => v.session);
  const [sessions, setSessions, getSessions] = useGetState<
    IAgentScopeRuntimeWebUISession[]
  >([]);
  const [currentSessionId, setCurrentSessionId, getCurrentSessionId] =
    useGetState<string | undefined>(undefined);

  useMount(async () => {
    const sessionList = await options.api.getSessionList();
    setSessions(sessionList);
    setCurrentSessionId(sessionList?.[0]?.id);
  });

  return (
    <ChatAnywhereSessionsContext.Provider
      value={{
        sessions,
        setSessions,
        getSessions,
        currentSessionId,
        setCurrentSessionId,
        getCurrentSessionId,
      }}
    >
      {props.children}
    </ChatAnywhereSessionsContext.Provider>
  );
}

/**
 * 会话切换时加载消息和判断重连的 hook，必须保证只挂载一次
 */
export const useChatAnywhereSessionLoader = () => {
  const currentSessionId = useContextSelector(
    ChatAnywhereSessionsContext,
    (v) => v.currentSessionId,
  );
  const options = useChatAnywhereOptions((v) => v.session);
  const setMessages = useContextSelector(
    ChatAnywhereMessagesContext,
    (v) => v.setMessages,
  );
  const getCurrentSessionId = useContextSelector(
    ChatAnywhereSessionsContext,
    (v) => v.getCurrentSessionId,
  );

  useAsyncEffect(async () => {
    await loadSessionMessages({
      requestedSessionId: currentSessionId,
      clearBeforeLoad: true,
      options,
      setMessages,
      getCurrentSessionId,
    });
  }, [currentSessionId]);
};

/**
 * 获取会话列表的 reactive 状态，供外部自定义会话面板使用
 */
export const useChatAnywhereSessionsState = () => {
  return useContextSelector(ChatAnywhereSessionsContext, (v) => v);
};

export const useChatAnywhereSessions = () => {
  const {
    setSessions,
    getSessions,
    getCurrentSessionId,
    setCurrentSessionId,
    currentSessionId,
  } = useContextSelector(ChatAnywhereSessionsContext, (v) => v);
  const options = useChatAnywhereOptions((v) => v.session);
  const setMessages = useContextSelector(
    ChatAnywhereMessagesContext,
    (v) => v.setMessages,
  );

  const removeSession = React.useCallback(
    async (
      session: Partial<IAgentScopeRuntimeWebUISession> & { id: string },
    ) => {
      const res = await options.api.removeSession(session);
      setMessages([]);
      setCurrentSessionId(undefined);
      setSessions(res);
    },
    [],
  );

  const updateSession = React.useCallback(
    async (session: Partial<IAgentScopeRuntimeWebUISession>) => {
      const res = session.id
        ? await options.api.updateSession(session)
        : await options.api.createSession(session);

      setSessions(res);
      return session;
    },
    [],
  );

  const createSession = React.useCallback(async (data?: { name?: string }) => {
    const session = await updateSession({
      name: data?.name || "",
      messages: [],
    });
    setCurrentSessionId(session.id);
    setMessages(session.messages);
    return session.id;
  }, []);

  const changeCurrentSessionId = React.useCallback((sessionId: string) => {
    setCurrentSessionId(sessionId);
  }, []);

  const refreshSession = React.useCallback(
    async (sessionId?: string) => {
      const requestedSessionId = sessionId ?? getCurrentSessionId();
      return loadSessionMessages({
        requestedSessionId,
        clearBeforeLoad: false,
        options,
        setMessages,
        getCurrentSessionId,
      });
    },
    [getCurrentSessionId, options, setMessages],
  );

  return {
    changeCurrentSessionId,
    getCurrentSessionId,
    getSessions,
    removeSession,
    updateSession,
    createSession,
    refreshSession,
  };
};
