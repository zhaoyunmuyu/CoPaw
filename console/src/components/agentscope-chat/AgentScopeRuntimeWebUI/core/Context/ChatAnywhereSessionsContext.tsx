import { createContext, useContextSelector } from "use-context-selector";
import { IAgentScopeRuntimeWebUISessionsContext } from "../types/ISessions";
import { IAgentScopeRuntimeWebUISessionAPI, IAgentScopeRuntimeWebUIMessage } from "../types";
import { useGetState, useMount } from "ahooks";
import { IAgentScopeRuntimeWebUISession } from "../types/ISessions";
import React from "react";
import { ChatAnywhereMessagesContext } from "./ChatAnywhereMessagesContext";
import { useChatAnywhereOptions } from "./ChatAnywhereOptionsContext";
import ReactDOM from "react-dom";
import { useAsyncEffect } from "ahooks";
import { emit } from "./useChatAnywhereEventEmitter";
import { getInitialSessionId } from "@/pages/Chat/sessionApi/initialSessionSelection";
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
  setMessages: (messages: IAgentScopeRuntimeWebUIMessage[]) => void;
  getCurrentSessionId: () => string | undefined;
  setSessionLoading?: (loading: boolean) => void;
}

async function loadSessionMessages({
  requestedSessionId,
  clearBeforeLoad,
  options,
  setMessages,
  getCurrentSessionId,
  setSessionLoading,
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
    // 使用 flushSync 确保 loading 状态和消息清空同步更新
    // 避免 React 状态更新异步导致先显示欢迎页再显示 loading
    ReactDOM.flushSync(() => {
      setSessionLoading?.(true);
      setMessages([]);
    });
  } else {
    setSessionLoading?.(true);
  }

  try {
    const session = await options.api.getSession(requestedSessionId);
    if (
      !shouldApplySessionLoadResult({
        requestedSessionId,
        currentSessionId: getCurrentSessionId(),
      })
    ) {
      // 竞态条件：当前会话已变更，此请求结果不应用
      // 不清除 loading，因为另一个请求正在加载当前会话
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
  } finally {
    // 只有当请求成功应用时才清除 loading
    // 竞态失败的请求不应清除 loading，让获胜的请求来清除
    const currentId = getCurrentSessionId();
    if (requestedSessionId === currentId) {
      setSessionLoading?.(false);
    }
  }
}

export const ChatAnywhereSessionsContext =
  createContext<IAgentScopeRuntimeWebUISessionsContext>({
    sessions: [],
    setSessions: () => {},
    getSessions: () => [],
    currentSessionId: undefined,
    setCurrentSessionId: () => {},
    getCurrentSessionId: () => "",
    isSessionLoading: false,
    setSessionLoading: () => {},
    isSessionsListLoading: true,
    setSessionsListLoading: () => {},
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
  const [isSessionLoading, setSessionLoading] = useGetState<boolean>(false);
  const [isSessionsListLoading, setSessionsListLoading] = useGetState<boolean>(true);

  useMount(async () => {
    setSessionsListLoading(true);
    try {
      const sessionList = await options.api.getSessionList();
      setSessions(sessionList);
      setCurrentSessionId(
        getInitialSessionId({
          pathname: window.location.pathname,
          sessionList,
        }),
      );
    } finally {
      setSessionsListLoading(false);
    }
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
        isSessionLoading,
        setSessionLoading,
        isSessionsListLoading,
        setSessionsListLoading,
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
  const setSessionLoading = useContextSelector(
    ChatAnywhereSessionsContext,
    (v) => v.setSessionLoading,
  );

  useAsyncEffect(async () => {
    await loadSessionMessages({
      requestedSessionId: currentSessionId,
      clearBeforeLoad: true,
      options,
      setMessages,
      getCurrentSessionId,
      setSessionLoading,
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
