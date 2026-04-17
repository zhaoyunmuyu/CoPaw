// ==================== 组件引入方式变更 (Kun He) ====================
import {
  AgentScopeRuntimeWebUI,
  IAgentScopeRuntimeWebUIOptions,
  type IAgentScopeRuntimeWebUIRef,
  useChatAnywhereSessionsState,
} from "@/components/agentscope-chat";
// ==================== 组件引入方式变更结束 ====================
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button, Modal, Result, Tooltip } from "antd";
import { useAppMessage } from "../../hooks/useAppMessage";
import { ExclamationCircleOutlined, SettingOutlined } from "@ant-design/icons";
import { SparkCopyLine, SparkAttachmentLine } from "@agentscope-ai/icons";
import { useTranslation } from "react-i18next";
import { useLocation, useNavigate } from "react-router-dom";
import sessionApi from "./sessionApi";
import defaultConfig, { getDefaultConfig } from "./OptionsPanel/defaultConfig";
import { chatApi } from "../../api/modules/chat";
import { cronJobApi } from "../../api/modules/cronjob";
import { getApiUrl } from "../../api/config";
import { buildAuthHeaders } from "../../api/authHeaders";
import { providerApi } from "../../api/modules/provider";
import type { ProviderInfo, ModelInfo, CronJobSpecOutput } from "../../api/types";
import ModelSelector from "./ModelSelector";
import { useTheme } from "../../contexts/ThemeContext";
import { useAgentStore } from "../../stores/agentStore";
// ==================== 组件引入方式变更 (Kun He) ====================
import { useChatAnywhereInput } from "@/components/agentscope-chat";
import DragUploadOverlay from "@/components/agentscope-chat/DragUploadOverlay";
// ==================== 组件引入方式变更结束 ====================
// ==================== userId 统一整改 (Kun He) ====================
// 使用统一的 getUserId/getChannel helper
import { getUserId, getChannel } from "../../utils/identity";
// ==================== userId 统一整改结束 ====================
// ==================== 品牌主题 (Kun He) ====================
import { useBrandTheme } from "../../contexts/BrandThemeContext";
// ==================== 品牌主题结束 ====================
// ==================== URL 导航参数 (Kun He, 2026-04-15) ====================
import { useIframeStore } from "../../stores/iframeStore";
// ==================== URL 导航参数结束 ====================
import styles from "./index.module.less";
import { IconButton } from "@agentscope-ai/design";
import ChatActionGroup from "./components/ChatActionGroup";
import ChatHeaderTitle from "./components/ChatHeaderTitle";
import ChatSessionInitializer from "./components/ChatSessionInitializer";
// ==================== 首页改版 (Kun He) ====================
import WelcomeCenterLayout from "@/components/agentscope-chat/WelcomeCenterLayout";
import ChatSidebar from "./components/ChatSidebar";
// ==================== 首页改版结束 ====================
import {
  toDisplayUrl,
  copyText,
  extractCopyableText,
  buildModelError,
  normalizeContentUrls,
  extractUserMessageText,
  type CopyableResponse,
  type RuntimeLoadingBridgeApi,
} from "./utils";
import { deriveChatTaskState, shouldMarkTaskReadOnOpen } from "./taskJobs";
import { shouldRefreshCurrentTaskMessages } from "./taskMessageRefresh";

const CHAT_ATTACHMENT_MAX_MB = 10;
const TASK_PAGE_POLL_MS = 30_000;
const TASK_PENDING_POLL_MS = 30_000;

interface SessionInfo {
  session_id?: string;
  user_id?: string;
  channel?: string;
}

interface CustomWindow extends Window {
  currentSessionId?: string;
  currentUserId?: string;
  currentChannel?: string;
}

declare const window: CustomWindow;

interface CommandSuggestion {
  command: string;
  value: string;
  description: string;
}

function renderSuggestionLabel(command: string, description: string) {
  return (
    <div className={styles.suggestionLabel}>
      <span className={styles.suggestionCommand}>{command}</span>
      <span className={styles.suggestionDescription}>{description}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

// ==================== userId 统一整改 (Kun He) ====================
// DEFAULT_USER_ID 和 DEFAULT_CHANNEL 已移至 constants/identity.ts
// 通过 getUserId() 和 getChannel() 获取
// ==================== userId 统一整改结束 ====================

// ---------------------------------------------------------------------------
// Custom hooks
// ---------------------------------------------------------------------------

/** Handle IME composition events to prevent premature Enter key submission. */
function useIMEComposition(isChatActive: () => boolean) {
  const isComposingRef = useRef(false);

  useEffect(() => {
    const handleCompositionStart = () => {
      if (!isChatActive()) return;
      isComposingRef.current = true;
    };

    const handleCompositionEnd = () => {
      if (!isChatActive()) return;
      // Use a slightly longer delay for Safari on macOS, which fires keydown
      // after compositionend within the same event loop tick.
      setTimeout(() => {
        isComposingRef.current = false;
      }, 200);
    };

    const suppressImeEnter = (e: KeyboardEvent) => {
      if (!isChatActive()) return;
      const target = e.target as HTMLElement;
      if (target?.tagName === "TEXTAREA" && e.key === "Enter" && !e.shiftKey) {
        // e.isComposing is the standard flag; isComposingRef covers the
        // post-compositionend grace period needed by Safari.
        if (isComposingRef.current || (e as any).isComposing) {
          e.stopPropagation();
          e.stopImmediatePropagation();
          e.preventDefault();
          return false;
        }
      }
    };

    document.addEventListener("compositionstart", handleCompositionStart, true);
    document.addEventListener("compositionend", handleCompositionEnd, true);
    // Listen on both keydown (Safari) and keypress (legacy) in capture phase.
    document.addEventListener("keydown", suppressImeEnter, true);
    document.addEventListener("keypress", suppressImeEnter, true);

    return () => {
      document.removeEventListener(
        "compositionstart",
        handleCompositionStart,
        true,
      );
      document.removeEventListener(
        "compositionend",
        handleCompositionEnd,
        true,
      );
      document.removeEventListener("keydown", suppressImeEnter, true);
      document.removeEventListener("keypress", suppressImeEnter, true);
    };
  }, [isChatActive]);

  return isComposingRef;
}

/** Fetch and track multimodal capabilities for the active model. */
function useMultimodalCapabilities(
  refreshKey: number,
  locationPathname: string,
  isChatActive: () => boolean,
  selectedAgent: string,
) {
  const [multimodalCaps, setMultimodalCaps] = useState<{
    supportsMultimodal: boolean;
    supportsImage: boolean;
    supportsVideo: boolean;
  }>({ supportsMultimodal: false, supportsImage: false, supportsVideo: false });

  const fetchMultimodalCaps = useCallback(async () => {
    try {
      const [providers, activeModels] = await Promise.all([
        providerApi.listProviders(),
        providerApi.getActiveModels({
          scope: "effective",
          agent_id: selectedAgent,
        }),
      ]);
      const activeProviderId = activeModels?.active_llm?.provider_id;
      const activeModelId = activeModels?.active_llm?.model;
      if (!activeProviderId || !activeModelId) {
        setMultimodalCaps({
          supportsMultimodal: false,
          supportsImage: false,
          supportsVideo: false,
        });
        return;
      }
      const provider = (providers as ProviderInfo[]).find(
        (p) => p.id === activeProviderId,
      );
      if (!provider) {
        setMultimodalCaps({
          supportsMultimodal: false,
          supportsImage: false,
          supportsVideo: false,
        });
        return;
      }
      const allModels: ModelInfo[] = [
        ...(provider.models ?? []),
        ...(provider.extra_models ?? []),
      ];
      const model = allModels.find((m) => m.id === activeModelId);
      setMultimodalCaps({
        supportsMultimodal: model?.supports_multimodal ?? false,
        supportsImage: model?.supports_image ?? false,
        supportsVideo: model?.supports_video ?? false,
      });
    } catch {
      setMultimodalCaps({
        supportsMultimodal: false,
        supportsImage: false,
        supportsVideo: false,
      });
    }
  }, [selectedAgent]);

  // Fetch caps on mount and whenever refreshKey changes
  useEffect(() => {
    fetchMultimodalCaps();
  }, [fetchMultimodalCaps, refreshKey]);

  // Also poll caps when navigating back to chat
  useEffect(() => {
    if (isChatActive()) {
      fetchMultimodalCaps();
    }
  }, [locationPathname, fetchMultimodalCaps, isChatActive]);

  // Listen for model-switched event from ModelSelector
  useEffect(() => {
    const handler = () => {
      fetchMultimodalCaps();
    };
    window.addEventListener("model-switched", handler);
    return () => window.removeEventListener("model-switched", handler);
  }, [fetchMultimodalCaps]);

  return multimodalCaps;
}

function RuntimeLoadingBridge({
  bridgeRef,
}: {
  bridgeRef: { current: RuntimeLoadingBridgeApi | null };
}) {
  const { setLoading, getLoading } = useChatAnywhereInput(
    (value) =>
      ({
        setLoading: value.setLoading,
        getLoading: value.getLoading,
      }) as RuntimeLoadingBridgeApi,
  );

  useEffect(() => {
    if (!setLoading || !getLoading) {
      bridgeRef.current = null;
      return;
    }

    bridgeRef.current = {
      setLoading,
      getLoading,
    };

    return () => {
      if (bridgeRef.current?.setLoading === setLoading) {
        bridgeRef.current = null;
      }
    };
  }, [getLoading, setLoading, bridgeRef]);

  return null;
}

export default function ChatPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const { isDark } = useTheme();
  // ==================== 品牌主题 (Kun He) ====================
  // 获取动态品牌配置，用于 welcome avatar
  const { theme: brandTheme } = useBrandTheme();
  // ==================== 品牌主题结束 ====================
  const chatId = useMemo(() => {
    const match = location.pathname.match(/^\/chat\/(.+)$/);
    return match?.[1];
  }, [location.pathname]);
  const [showModelPrompt, setShowModelPrompt] = useState(false);
  const [jobs, setJobs] = useState<CronJobSpecOutput[]>([]);
  const { selectedAgent } = useAgentStore();
  const [refreshKey, setRefreshKey] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const dragCounterRef = useRef(0);
  const runtimeLoadingBridgeRef = useRef<RuntimeLoadingBridgeApi | null>(null);
  const { message } = useAppMessage();
  const { setSessionLoading } = useChatAnywhereSessionsState();

  const isChatActiveRef = useRef(false);
  isChatActiveRef.current =
    location.pathname === "/" || location.pathname.startsWith("/chat");

  const isChatActive = useCallback(() => isChatActiveRef.current, []);

  // Use custom hooks for better separation of concerns
  const isComposingRef = useIMEComposition(isChatActive);
  const multimodalCaps = useMultimodalCapabilities(
    refreshKey,
    location.pathname,
    isChatActive,
    selectedAgent,
  );

  const lastSessionIdRef = useRef<string | null>(null);
  /** Tracks the stale auto-selected session ID that was skipped on init, so we can suppress its late-arriving onSessionSelected callback. */
  const staleAutoSelectedIdRef = useRef<string | null>(null);
  const taskHadResultRef = useRef(false);
  const previousCurrentTaskRef = useRef<CronJobSpecOutput | null>(null);
  const chatIdRef = useRef(chatId);
  const navigateRef = useRef(navigate);
  const chatRef = useRef<IAgentScopeRuntimeWebUIRef>(null);
  chatIdRef.current = chatId;
  navigateRef.current = navigate;

  // Tell sessionApi which session to put first in getSessionList, so the library's
  // useMount auto-selects the correct session without an extra getSession round-trip.
  if (chatId && sessionApi.preferredChatId !== chatId) {
    sessionApi.preferredChatId = chatId;
  }

  // Register session API event callbacks for URL synchronization

  useEffect(() => {
    sessionApi.onSessionIdResolved = (realId) => {
      if (!isChatActiveRef.current) return;
      // Update URL when realId is resolved, regardless of current chatId
      // (chatId may be undefined if URL was cleared in onSessionCreated)
      lastSessionIdRef.current = realId;
      navigateRef.current(`/chat/${realId}`, { replace: true });
    };

    sessionApi.onSessionRemoved = (removedId) => {
      if (!isChatActiveRef.current) return;
      // Clear URL when current session is removed
      // Check if removed session matches current session (by realId or sessionId)
      const currentRealId = sessionApi.getRealIdForSession(
        chatIdRef.current || "",
      );
      if (chatIdRef.current === removedId || currentRealId === removedId) {
        lastSessionIdRef.current = null;
        navigateRef.current("/chat", { replace: true });
      }
    };

    sessionApi.onSessionSelected = (
      sessionId: string | null | undefined,
      realId: string | null,
    ) => {
      if (!isChatActiveRef.current) return;
      // Update URL when session is selected and different from current
      const targetId = realId || sessionId;
      if (!targetId) return;

      // If current URL's chatId differs from targetId, skip this callback.
      // This happens when user quickly switches sessions via sidebar:
      // 1. User clicks A → getSession(A) starts
      // 2. User clicks B → URL becomes /chat/B
      // 3. A's request completes → onSessionSelected(A) fires
      // 4. Should NOT navigate back to A since user already chose B
      const currentUrlChatId = chatIdRef.current;
      if (currentUrlChatId && currentUrlChatId !== targetId) {
        return;
      }

      // If a preferred chatId from the URL exists and no navigation has happened yet,
      // skip the library's initial auto-selection (always first session).
      // ChatSessionInitializer will apply the correct selection afterward.
      if (
        chatIdRef.current &&
        lastSessionIdRef.current === null &&
        targetId !== chatIdRef.current
      ) {
        lastSessionIdRef.current = targetId;
        // Record the stale ID so its delayed getSession callback is also suppressed.
        staleAutoSelectedIdRef.current = targetId;
        return;
      }

      // Suppress the stale getSession callback that arrives after the correct session loads.
      if (
        staleAutoSelectedIdRef.current &&
        staleAutoSelectedIdRef.current === targetId
      ) {
        staleAutoSelectedIdRef.current = null;
        return;
      }

      if (targetId !== lastSessionIdRef.current) {
        lastSessionIdRef.current = targetId;
        navigateRef.current(`/chat/${targetId}`, { replace: true });
      }
    };

    sessionApi.onSessionCreated = () => {
      if (!isChatActiveRef.current) return;
      // Clear URL when creating new session, wait for realId resolution to update
      lastSessionIdRef.current = null;
      navigateRef.current("/chat", { replace: true });
    };

    return () => {
      sessionApi.onSessionIdResolved = null;
      sessionApi.onSessionRemoved = null;
      sessionApi.onSessionSelected = null;
      sessionApi.onSessionCreated = null;
    };
  }, []);

  // ==================== URL 导航参数 (Kun He, 2026-04-15) ====================
  // 处理 iframe URL 传递的 sessionId/taskId 参数，自动跳转到对应聊天页面
  // sessionId: 直接导航到 /chat/:sessionId
  // taskId: 查找 task.chat_id 后导航
  const sessionIdRef = useRef<string | null>(null);
  const taskIdRef = useRef<string | null>(null);

  useEffect(() => {
    const store = useIframeStore.getState();
    const { sessionId, taskId } = store;

    // 只在首次加载时处理，避免重复导航
    if (sessionId) {
      sessionIdRef.current = sessionId;
      taskIdRef.current = null; // sessionId 优先，忽略 taskId
      store.clearNavigationParams();
      console.info("[Chat] Navigating to sessionId:", sessionId);
      navigate(`/chat/${sessionId}`, { replace: true });
      return;
    }

    if (taskId) {
      taskIdRef.current = taskId;
      store.clearNavigationParams();
      console.info("[Chat] taskId set, waiting for jobs:", taskId);
    }
  }, [navigate]);

  // taskId 导航需要等待 jobs 加载完成
  useEffect(() => {
    if (!taskIdRef.current || jobs.length === 0) return;

    const task = jobs.find((j) => j.id === taskIdRef.current);
    const chatId = task?.task?.chat_id;

    if (chatId) {
      console.info("[Chat] Navigating from taskId to chatId:", {
        taskId: taskIdRef.current,
        chatId,
      });
      navigate(`/chat/${chatId}`, { replace: true });
      taskIdRef.current = null;
    } else {
      console.warn("[Chat] taskId not found or no chat_id:", taskIdRef.current);
      taskIdRef.current = null;
    }
  }, [jobs, navigate]);
  // ==================== URL 导航参数结束 ====================

  // Setup multimodal capabilities tracking via custom hook

  // Refresh chat when selectedAgent changes
  const prevSelectedAgentRef = useRef(selectedAgent);
  useEffect(() => {
    // Only refresh if selectedAgent actually changed (not initial mount)
    if (
      prevSelectedAgentRef.current !== selectedAgent &&
      prevSelectedAgentRef.current !== undefined
    ) {
      // Force re-render by updating refresh key
      setRefreshKey((prev) => prev + 1);
    }
    prevSelectedAgentRef.current = selectedAgent;
  }, [selectedAgent]);

  const refreshJobs = useCallback(async () => {
    try {
      const nextJobs = await cronJobApi.listCronJobs();
      setJobs(Array.isArray(nextJobs) ? nextJobs : []);
    } catch {
      setJobs([]);
    }
  }, []);

  const { tasks, currentTask } = useMemo(
    () => deriveChatTaskState(jobs, chatId),
    [jobs, chatId],
  );

  useEffect(() => {
    void refreshJobs();

    const handleFocusRefresh = () => {
      void refreshJobs();
    };
    const handleVisibilityRefresh = () => {
      if (document.visibilityState === "visible") {
        void refreshJobs();
      }
    };

    window.addEventListener("focus", handleFocusRefresh);
    document.addEventListener("visibilitychange", handleVisibilityRefresh);

    return () => {
      window.removeEventListener("focus", handleFocusRefresh);
      document.removeEventListener("visibilitychange", handleVisibilityRefresh);
    };
  }, [refreshJobs]);

  useEffect(() => {
    const pollMs =
      currentTask?.task?.has_scheduled_result === false
        ? TASK_PENDING_POLL_MS
        : TASK_PAGE_POLL_MS;

    const intervalId = window.setInterval(() => {
      void refreshJobs();
    }, pollMs);

    return () => window.clearInterval(intervalId);
  }, [currentTask?.task?.has_scheduled_result, refreshJobs]);

  useEffect(() => {
    const hadResult = Boolean(currentTask?.task?.has_scheduled_result);
    if (hadResult && !taskHadResultRef.current) {
      setRefreshKey((prev) => prev + 1);
    }
    taskHadResultRef.current = hadResult;
  }, [currentTask?.task?.has_scheduled_result]);

  useEffect(() => {
    if (!currentTask?.id) return;
    if ((currentTask.task?.unread_execution_count || 0) <= 0) return;
    if (!shouldMarkTaskReadOnOpen(currentTask)) return;

    setJobs((prev) =>
      prev.map((job) =>
        job.id === currentTask.id && job.task
          ? {
              ...job,
              task: {
                ...job.task,
                unread_execution_count: 0,
              },
            }
          : job,
      ),
    );
    void cronJobApi.markTaskRead(currentTask.id).catch(() => {});
  }, [currentTask?.id, currentTask?.task?.unread_execution_count]);

  const handleTaskOpen = useCallback(
    async (task: CronJobSpecOutput) => {
      const taskChatId = task.task?.chat_id;
      if (!taskChatId) return;

      if (shouldMarkTaskReadOnOpen(task)) {
        setJobs((prev) =>
          prev.map((job) =>
            job.id === task.id && job.task
              ? {
                  ...job,
                  task: {
                    ...job.task,
                    unread_execution_count: 0,
                  },
                }
              : job,
          ),
        );
      }

      // 先设置 loading 状态，避免导航后闪现欢迎页
      setSessionLoading(true);
      navigate(`/chat/${taskChatId}`, { replace: true });

      if (shouldMarkTaskReadOnOpen(task)) {
        try {
          await cronJobApi.markTaskRead(task.id);
        } catch {
          void refreshJobs();
        }
      }
    },
    [navigate, refreshJobs, setSessionLoading],
  );

  const handleTaskResume = useCallback(
    async (task: CronJobSpecOutput) => {
      setJobs((prev) =>
        prev.map((job) =>
          job.id === task.id
            ? {
                ...job,
                enabled: true,
                task: job.task
                  ? {
                      ...job.task,
                      is_paused: false,
                      pause_reason: null,
                      auto_paused_at: null,
                      unread_execution_count: 0,
                    }
                  : job.task,
              }
            : job,
        ),
      );

      try {
        await cronJobApi.resumeCronJob(task.id);
        message.success("任务已恢复");
        void refreshJobs();
      } catch {
        message.error("恢复失败");
        void refreshJobs();
      }
    },
    [message, refreshJobs],
  );

  const handleTaskDelete = useCallback(
    (task: CronJobSpecOutput) => {
      Modal.confirm({
        title: "删除暂停任务",
        content: `确认删除任务“${task.name || task.id}”？`,
        okText: "删除",
        okType: "danger",
        cancelText: "取消",
        onOk: async () => {
          setJobs((prev) => prev.filter((job) => job.id !== task.id));
          if (task.task?.chat_id && task.task.chat_id === chatIdRef.current) {
            navigate("/chat", { replace: true });
          }
          try {
            await cronJobApi.deleteCronJob(task.id);
            message.success("任务已删除");
            void refreshJobs();
          } catch {
            message.error("删除失败");
            void refreshJobs();
          }
        },
      });
    },
    [message, navigate, refreshJobs],
  );

  useEffect(() => {
    const previousTask = previousCurrentTaskRef.current;
    previousCurrentTaskRef.current = currentTask;

    if (
      !shouldRefreshCurrentTaskMessages({
        previousTask,
        currentTask,
      })
    ) {
      return;
    }

    void chatRef.current?.refreshSession?.();
  }, [
    currentTask?.id,
    currentTask?.task?.has_scheduled_result,
    currentTask?.task?.last_scheduled_run_at,
    currentTask?.task?.unread_execution_count,
  ]);

  // Show toast when task has no scheduled result yet
  const taskNoResultShownRef = useRef(false);
  useEffect(() => {
    if (currentTask && !currentTask.task?.has_scheduled_result) {
      if (!taskNoResultShownRef.current) {
        taskNoResultShownRef.current = true;
        message.info("当前任务暂未启动，等下次收到提醒再来看看哟~");
      }
    } else {
      taskNoResultShownRef.current = false;
    }
  }, [currentTask?.id, currentTask?.task?.has_scheduled_result]);

  const copyResponse = useCallback(
    async (response: CopyableResponse) => {
      try {
        await copyText(extractCopyableText(response));
        message.success(t("common.copied"));
      } catch {
        message.error(t("common.copyFailed"));
      }
    },
    [t],
  );

  const customFetch = useCallback(
    async (data: {
      input?: Array<Record<string, unknown>>;
      biz_params?: Record<string, unknown>;
      signal?: AbortSignal;
    }): Promise<Response> => {
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
        ...buildAuthHeaders(),
      };

      try {
        const activeModels = await providerApi.getActiveModels({
          scope: "effective",
          agent_id: selectedAgent,
        });
        if (
          !activeModels?.active_llm?.provider_id ||
          !activeModels?.active_llm?.model
        ) {
          setShowModelPrompt(true);
          return buildModelError();
        }
      } catch {
        setShowModelPrompt(true);
        return buildModelError();
      }

      const { input = [], biz_params } = data;
      const session: SessionInfo = input[input.length - 1]?.session || {};
      const lastInput = input.slice(-1);
      const lastMsg = lastInput[0];
      const rewrittenInput =
        lastMsg?.content && Array.isArray(lastMsg.content)
          ? [
              {
                ...lastMsg,
                content: lastMsg.content.map(normalizeContentUrls),
              },
            ]
          : lastInput;

      const requestBody = {
        input: rewrittenInput,
        session_id: window.currentSessionId || session?.session_id || "",
        // ==================== userId 统一整改 (Kun He) ====================
        // 使用 getUserId()/getChannel() 获取，优先级：iframe > window > session > default
        user_id: getUserId(session?.user_id),
        channel: getChannel(session?.channel),
        // ==================== userId 统一整改结束 ====================
        stream: true,
        ...biz_params,
      };

      const backendChatId =
        sessionApi.getRealIdForSession(requestBody.session_id) ??
        chatIdRef.current ??
        requestBody.session_id;
      if (backendChatId) {
        const userText = rewrittenInput
          .filter((m: any) => m.role === "user")
          .map(extractUserMessageText)
          .join("\n")
          .trim();
        if (userText) {
          sessionApi.setLastUserMessage(backendChatId, userText);
        }
      }

      const response = await fetch(getApiUrl("/console/chat"), {
        method: "POST",
        headers,
        body: JSON.stringify(requestBody),
        signal: data.signal,
      });

      return response;
    },
    [selectedAgent],
  );

  const handleFileUpload = useCallback(
    async (options: {
      file: File;
      onSuccess: (body: { url?: string; thumbUrl?: string }) => void;
      onError?: (e: Error) => void;
      onProgress?: (e: { percent?: number }) => void;
    }) => {
      const { file, onSuccess, onError, onProgress } = options;
      try {
        // Warn when model has no multimodal support
        if (!multimodalCaps.supportsMultimodal) {
          message.warning(t("chat.attachments.multimodalWarning"));
        } else if (
          multimodalCaps.supportsImage &&
          !multimodalCaps.supportsVideo &&
          !file.type.startsWith("image/")
        ) {
          // Warn (not block) when only image is supported
          message.warning(t("chat.attachments.imageOnlyWarning"));
        }
        const sizeMb = file.size / 1024 / 1024;
        const isWithinLimit = sizeMb < CHAT_ATTACHMENT_MAX_MB;

        if (!isWithinLimit) {
          message.error(
            t("chat.attachments.fileSizeExceeded", {
              limit: CHAT_ATTACHMENT_MAX_MB,
              size: sizeMb.toFixed(2),
            }),
          );
          onError?.(new Error(`File size exceeds ${CHAT_ATTACHMENT_MAX_MB}MB`));
          return;
        }

        const res = await chatApi.uploadFile(file);
        onProgress?.({ percent: 100 });
        onSuccess({ url: chatApi.filePreviewUrl(res.url) });
      } catch (e) {
        onError?.(e instanceof Error ? e : new Error(String(e)));
      }
    },
    [multimodalCaps, t],
  );

  // ==================== Drag & drop file upload (Kun He) ====================
  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.dataTransfer.types.includes("Files")) {
      dragCounterRef.current += 1;
      if (dragCounterRef.current === 1) {
        setIsDragging(true);
      }
    }
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current -= 1;
    if (dragCounterRef.current === 0) {
      setIsDragging(false);
    }
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current = 0;
    setIsDragging(false);

    const files = Array.from(e.dataTransfer.files);
    for (const file of files) {
      document.dispatchEvent(
        new CustomEvent("pasteFile", {
          detail: { file },
        }),
      );
    }
  }, []);

  const handleDragOverlayClose = useCallback(() => {
    dragCounterRef.current = 0;
    setIsDragging(false);
  }, []);
  // ==================== Drag & drop end ====================

  const options = useMemo(() => {
    const i18nConfig = getDefaultConfig(t);
    const commandSuggestions: CommandSuggestion[] = [
      {
        command: "/clear",
        value: "clear",
        description: t("chat.commands.clear.description"),
      },
      {
        command: "/compact",
        value: "compact",
        description: t("chat.commands.compact.description"),
      },
      {
        command: "/approve",
        value: "approve",
        description: t("chat.commands.approve.description"),
      },
      {
        command: "/deny",
        value: "deny",
        description: t("chat.commands.deny.description"),
      },
    ];

    const handleBeforeSubmit = async () => {
      if (isComposingRef.current) return false;
      return true;
    };

    return {
      ...i18nConfig,
      theme: {
        ...defaultConfig.theme,
        darkMode: isDark,
        leftHeader: {
          ...defaultConfig.theme.leftHeader,
        },
        rightHeader: (
          <>
            <ChatSessionInitializer />
            <RuntimeLoadingBridge bridgeRef={runtimeLoadingBridgeRef} />
            <ChatHeaderTitle />
            <span style={{ flex: 1 }} />
            <ModelSelector />
            <ChatActionGroup />
          </>
        ),
      },
      welcome: {
        ...i18nConfig.welcome,
        nick: brandTheme.brandName,
        // ==================== 品牌主题 (Kun He) ====================
        // 使用动态品牌 avatar
        avatar: brandTheme.avatar
          ? `${import.meta.env.BASE_URL}${brandTheme.avatar.replace(/^\//, "")}`
          : undefined,
        // ==================== 品牌主题结束 ====================
        // ==================== 首页改版 (Kun He) ====================
        // 使用自定义欢迎页渲染，替代默认 WelcomePrompts
        render: ({ greeting, onSubmit }) => (
          <WelcomeCenterLayout
            greeting={
              typeof greeting === "string"
                ? greeting
                : "你好，你的专属小龙虾，前来报到！"
            }
            onSubmit={(data) => onSubmit(data)}
          />
        ),
        // ==================== 首页改版结束 ====================
      },
      sender: {
        ...(i18nConfig as any)?.sender,
        beforeSubmit: handleBeforeSubmit,
        allowSpeech: true,
        attachments: {
          trigger: function (props: any) {
            const tooltipKey = multimodalCaps.supportsMultimodal
              ? multimodalCaps.supportsImage && !multimodalCaps.supportsVideo
                ? "chat.attachments.tooltipImageOnly"
                : "chat.attachments.tooltip"
              : "chat.attachments.tooltipNoMultimodal";
            return (
              <Tooltip title={t(tooltipKey, { limit: CHAT_ATTACHMENT_MAX_MB })}>
                <IconButton
                  disabled={props?.disabled}
                  icon={<SparkAttachmentLine />}
                  bordered={false}
                />
              </Tooltip>
            );
          },
          accept: "*/*",
          customRequest: handleFileUpload,
        },
        placeholder: t("chat.inputPlaceholder"),
        suggestions: commandSuggestions.map((item) => ({
          label: renderSuggestionLabel(item.command, item.description),
          value: item.value,
        })),
      },
      session: {
        multiple: true,
        hideBuiltInSessionList: true,
        api: sessionApi,
      },
      api: {
        ...defaultConfig.api,
        fetch: customFetch,
        replaceMediaURL: (url: string) => {
          return toDisplayUrl(url);
        },
        cancel(data: { session_id: string }) {
          const chatId =
            sessionApi.getRealIdForSession(data.session_id) ?? data.session_id;
          if (chatId) {
            chatApi.stopChat(chatId).catch((err) => {
              console.error("Failed to stop chat:", err);
            });
          }
        },
        async reconnect(data: { session_id: string; signal?: AbortSignal }) {
          const headers: Record<string, string> = {
            "Content-Type": "application/json",
            ...buildAuthHeaders(),
          };

          return fetch(getApiUrl("/console/chat"), {
            method: "POST",
            headers,
            body: JSON.stringify({
              reconnect: true,
              session_id: window.currentSessionId || data.session_id,
              // ==================== userId 统一整改 (Kun He) ====================
              // 使用 getUserId()/getChannel() 获取
              user_id: getUserId(),
              channel: getChannel(),
              // ==================== userId 统一整改结束 ====================
            }),
            signal: data.signal,
          });
        },
      },
      actions: {
        list: [
          {
            icon: (
              <span title={t("common.copy")}>
                <SparkCopyLine />
              </span>
            ),
            onClick: ({ data }: { data: CopyableResponse }) => {
              void copyResponse(data);
            },
          },
        ],
        replace: true,
      },
    } as unknown as IAgentScopeRuntimeWebUIOptions;
  }, [customFetch, copyResponse, handleFileUpload, t, isDark, multimodalCaps]);

  // ==================== 首页改版 (Kun He) ====================
  // 新建聊天：通过 chatRef 调用后端 createSession API
  const handleCreateSessionFromSidebar = useCallback(async () => {
    const newId = await chatRef.current?.createSession?.();
    if (newId) {
      navigate(`/chat/${newId}`, { replace: true });
    } else {
      navigate("/chat", { replace: true });
    }
  }, [navigate]);
  // ==================== 首页改版结束 ====================

  return (
    <div
      style={{
        height: "100%",
        width: "100%",
        display: "flex",
        flexDirection: "row",
      }}
    >
      {/* ==================== 首页改版 (Kun He) ==================== */}
      {/* 聊天专用侧栏：支持折叠为64px工具条 */}
      <ChatSidebar
        tasks={tasks}
        onCreateSession={handleCreateSessionFromSidebar}
        onTaskClick={handleTaskOpen}
        onTaskResume={handleTaskResume}
        onTaskDelete={handleTaskDelete}
      />
      {/* ==================== 首页改版结束 ==================== */}
      <div
        className={styles.chatMessagesArea}
        style={{ flex: 1, minWidth: 0, position: "relative" }}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
      >
        <AgentScopeRuntimeWebUI
          ref={chatRef}
          key={refreshKey}
          options={options}
        />
        <DragUploadOverlay visible={isDragging} onClose={handleDragOverlayClose} />
      </div>

      <Modal
        open={showModelPrompt}
        closable={false}
        footer={null}
        width={480}
        styles={{
          content: isDark
            ? { background: "#1f1f1f", boxShadow: "0 8px 32px rgba(0,0,0,0.5)" }
            : undefined,
        }}
      >
        <Result
          icon={<ExclamationCircleOutlined style={{ color: "#faad14" }} />}
          title={
            <span
              style={{ color: isDark ? "rgba(255,255,255,0.88)" : undefined }}
            >
              {t("modelConfig.promptTitle")}
            </span>
          }
          subTitle={
            <span
              style={{ color: isDark ? "rgba(255,255,255,0.55)" : undefined }}
            >
              {t("modelConfig.promptMessage")}
            </span>
          }
          extra={[
            <Button key="skip" onClick={() => setShowModelPrompt(false)}>
              {t("modelConfig.skipButton")}
            </Button>,
            <Button
              key="configure"
              type="primary"
              icon={<SettingOutlined />}
              onClick={() => {
                setShowModelPrompt(false);
                navigate("/models");
              }}
            >
              {t("modelConfig.configureButton")}
            </Button>,
          ]}
        />
      </Modal>
    </div>
  );
}
