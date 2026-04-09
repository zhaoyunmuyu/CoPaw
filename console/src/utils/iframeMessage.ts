/**
 * ============================================================
 * iframe postMessage 通信核心逻辑
 * Author: Kun He
 * Date: 2026-04-07
 * ============================================================
 */
import type {
  IframeUserDataMessage,
  IframeIncomingMessage,
  IframeOutgoingMessage,
  AuthHeaderItem,
} from "../types/iframe";
import { useIframeStore, getIframeContext } from "../stores/iframeStore";
import {
  fetchCustomerInfo,
  fetchUserInit,
  isUserInitialized,
  setUserInitialized,
} from "../api/modules/customerInfo";

/**
 * 允许的来源白名单
 */
const ALLOWED_ORIGINS: string[] = [
  // 开发环境
  // "http://localhost:5173",
  // "http://127.0.0.1:5173",
  // 生产环境 - 从环境变量读取
  // ...(typeof import.meta !== "undefined" &&
  // import.meta.env?.VITE_ALLOWED_PARENT_ORIGINS
  //   ? import.meta.env.VITE_ALLOWED_PARENT_ORIGINS.split(",").filter(Boolean)
  //   : []),
];

/** 是否已注册监听器 */
let isListenerRegistered = false;

/** 清理函数 */
let cleanupFn: (() => void) | null = null;

/**
 * 将值转换为布尔值，用于处理父窗口可能传递的字符串 "true"/"false"
 * @param value - 值
 * @returns 布尔值
 */
function toBoolean(value: boolean | string | undefined): boolean {
  if (typeof value === "boolean") return value;
  if (typeof value === "string") return value.toLowerCase() === "true";
  return false;
}

/**
 * 验证消息来源是否可信
 * @param origin - 消息来源 origin
 * @returns 是否可信
 */
function isValidOrigin(origin: string): boolean {
  // 如果在 iframe 中运行
  if (window.self !== window.top) {
    // 严格模式：检查白名单，白名单为空则允许所有
    return ALLOWED_ORIGINS.length === 0 || ALLOWED_ORIGINS.includes(origin);
  }
  // 不在 iframe 中，不需要验证
  return true;
}

/**
 * 验证消息格式
 * @param data - 消息数据
 * @returns 是否为有效的 iframe 消息
 */
function validateMessage(data: unknown): data is IframeIncomingMessage {
  if (!data || typeof data !== "object") return false;
  const msg = data as Record<string, unknown>;

  // 必须有 type 字段且为字符串
  if (typeof msg.type !== "string") return false;

  // 根据类型验证
  switch (msg.type) {
    case "USER_DATA":
      // 所有参数均为可选，只要有 type 字段即可
      return true;
    case "HEARTBEAT":
      return typeof msg.timestamp === "number";
    case "READY_REQUEST":
      return true;
    default:
      // 未知类型，忽略但不报错
      return false;
  }
}

/**
 * 构建认证 headers
 * 将 sapId 作为 X-User-Id，并合并父窗口传递的 auth 数组
 */
function buildAuthHeaders(message: IframeUserDataMessage): AuthHeaderItem[] {
  const authHeaders = message.auth ?? [];
  if (message.sapId) {
    authHeaders.push({ headerName: "X-User-Id", headerValue: message.sapId });
  }
  return authHeaders;
}

/**
 * 调用客户信息查询接口并更新 store
 * 当 URL 参数 origin === "Y" 时触发
 */
async function fetchAndApplyCustomerInfo(
  userId: string,
  store: ReturnType<typeof useIframeStore.getState>,
): Promise<void> {
  try {
    const targetUserData = {
      inputParams: {
        userId,
        sysId: "",
        bbk: "",
        orgCode: "",
        orgLvl: "",
        positionId: "",
      },
    };
    const response = await fetchCustomerInfo(targetUserData);

    if (response?.returnCode === "SUC0000") {
      const result = response.body.output.result;
      if (result.userChange) {
        store.setContext({
          userId: result.userId ?? null,
          sysId: result.sysId ?? null,
          token: result.token ?? null,
          bbk: result.bbk ?? null,
          orgCode: result.orgCode ?? null,
          orgLvl: result.orgLvl ?? null,
          positionId: result.positionId ?? null,
        });
      }
    } else {
      console.warn("[IframeMessage] Customer info fetch failed:", response?.errorMsg);
    }
  } catch (error) {
    console.error("[IframeMessage] Customer info fetch error:", error);
  }
}

/**
 * 调用用户初始化接口并保存到 localStorage
 * 检查用户是否已初始化，未初始化则调用接口
 */
async function initializeUserIfNeeded(
  userId: string,
  store: ReturnType<typeof useIframeStore.getState>,
): Promise<void> {
  if (isUserInitialized(userId)) {
    return;
  }

  const params = {
    filename: "PROFILE.md",
    text: `\n### 用户身份信息\n分行号：${store.bbk}\n网点机构编号：${store.orgCode}\n岗位编号：${store.positionId}\n客户经理ID：${userId}`,
  };

  try {
    const initResponse = await fetchUserInit(params);

    if (initResponse?.success) {
      setUserInitialized(userId);
    } else {
      console.warn("[IframeMessage] User init failed");
    }
  } catch (error) {
    console.error("[IframeMessage] User init error:", error);
  }
}

/**
 * 处理 USER_DATA 消息
 * 父窗口发送的用户数据消息处理逻辑
 */
async function handleUserDataMessage(message: IframeUserDataMessage, origin: string): Promise<void> {
  const store = useIframeStore.getState();
  const authHeaders = buildAuthHeaders(message);

  store.setContext({
    userId: message.sapId ?? null,
    clawName: message.clawName ?? null,
    space: message.space ?? null,
    source: message.source ?? null,
    hideMenu: toBoolean(message.hideMenu),
    isSuperManager: toBoolean(message.isSuperManager),
    authHeaders,
    parentOrigin: origin,
  });

  const urlParams = new URLSearchParams(window.location.search);
  const originParam = urlParams.get("origin");

  if (originParam === "Y" && message.sapId) {
    await fetchAndApplyCustomerInfo(message.sapId, store);
    const currentUserId = store.userId;
    if (currentUserId) {
      await initializeUserIfNeeded(currentUserId, store);
    }
  }

  store.markInitialized();
  sendMessageToParent({ type: "READY_RESPONSE", initialized: true });

  console.info("[IframeMessage] Initialized with context from parent:", {
    origin,
    userId: message.sapId,
    clawName: message.clawName,
    space: message.space,
    source: message.source,
    hideMenu: message.hideMenu,
    isSuperManager: message.isSuperManager,
    authHeadersCount: authHeaders.length,
  });
}

/**
 * 处理心跳消息
 * @param timestamp - 心跳时间戳
 */
function handleHeartbeatMessage(timestamp: number): void {
  console.debug("[IframeMessage] Heartbeat received:", timestamp);
  // 可用于检测父窗口连接状态
}

/**
 * 处理就绪查询消息
 */
function handleReadyRequest(): void {
  const context = getIframeContext();
  sendMessageToParent({
    type: "READY_RESPONSE",
    initialized: context.initialized,
  });
}

/**
 * 消息处理中心
 * @param event - MessageEvent
 */
function handleMessage(event: MessageEvent): void {
  // 安全检查：验证来源
  if (!isValidOrigin(event.origin)) {
    console.warn(
      "[IframeMessage] Rejected message from untrusted origin:",
      event.origin,
    );
    return;
  }

  // 验证消息格式
  if (!validateMessage(event.data)) {
    console.debug("[IframeMessage] Ignored invalid message format");
    return;
  }

  const message = event.data as IframeIncomingMessage;

  switch (message.type) {
    case "USER_DATA":
      // handleUserDataMessage 是 async 函数，这里用 void 处理
      void handleUserDataMessage(message, event.origin);
      break;
    case "HEARTBEAT":
      handleHeartbeatMessage(message.timestamp);
      break;
    case "READY_REQUEST":
      handleReadyRequest();
      break;
  }
}

/**
 * 向父窗口发送消息
 * @param message - 出站消息
 */
export function sendMessageToParent(message: IframeOutgoingMessage): void {
  // 检查是否在 iframe 中
  if (window.parent === window.self) {
    return;
  }

  const context = getIframeContext();
  const targetOrigin = context.parentOrigin || "*";

  window.parent.postMessage(message, targetOrigin);
}

/**
 * 初始化 iframe 消息监听器
 * 应在 main.tsx 中尽早调用，确保不遗漏任何消息
 *
 * 初始化流程：
 * 1. 检查是否已在 iframe 中运行（非 iframe 环境跳过）
 * 2. 注册 message 事件监听器
 * 3. 发送 READY_RESPONSE (initialized: false) 通知父窗口
 * 4. 等待父窗口发送 USER_DATA 消息
 */
export function initIframeMessageListener(): void {
  // 防止重复注册
  if (isListenerRegistered) {
    console.warn("[IframeMessage] Listener already registered");
    return;
  }

  // 检查是否在 iframe 中
  if (window.self === window.top) {
    console.debug("[IframeMessage] Not running in iframe, skipping listener");
    return;
  }

  // 注册消息监听器
  window.addEventListener("message", handleMessage);
  isListenerRegistered = true;

  // 注册清理函数
  cleanupFn = () => {
    window.removeEventListener("message", handleMessage);
    isListenerRegistered = false;
    cleanupFn = null;
  };

  // 页面卸载时自动清理
  window.addEventListener("beforeunload", cleanupFn);

  console.info("[IframeMessage] Listener registered");

  // 通知父窗口准备就绪，可以发送初始化消息 (USER_DATA)
  // initialized: false 表示等待父窗口发送数据
  sendMessageToParent({ type: "READY_RESPONSE", initialized: false });
}

/**
 * 手动清理监听器
 *
 * 通常不需要手动调用，页面卸载时会自动清理
 * 仅在特殊场景（如测试）中使用
 */
export function cleanupIframeMessageListener(): void {
  if (cleanupFn) {
    cleanupFn();
    console.info("[IframeMessage] Listener cleaned up");
  }
}

/**
 * 检查是否在 iframe 中运行
 * @returns 是否在 iframe 中
 */
export function isInIframe(): boolean {
  return window.self !== window.top;
}

/**
 * 检查 iframe 上下文是否已初始化
 * @returns 是否已初始化
 */
export function isIframeInitialized(): boolean {
  return getIframeContext().initialized;
}

/**
 * 获取允许的来源白名单
 * @returns 来源白名单数组
 */
export function getAllowedOrigins(): string[] {
  return [...ALLOWED_ORIGINS];
}