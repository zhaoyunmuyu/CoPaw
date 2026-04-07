/**
 * iframe postMessage 通信类型定义
 *
 * 用于子应用与父级 iframe 应用之间的消息通信
 */

/**
 * 自定义 header 项
 * 用于父应用传递自定义 headers
 */
export interface AuthHeaderItem {
  headerName: string;
  headerValue: string;
}

/**
 * 用户数据消息
 * 父窗口发送给子窗口的初始化参数
 */
export interface IframeUserDataMessage {
  type: "USER_DATA";
  /** SAP ID，会作为 userId 存储 */
  sapId?: string;
  /** Claw 名称 */
  clawName?: string;
  /** 空间标识 */
  space?: string;
  /** 来源标识 */
  source?: string;
  /** 是否隐藏菜单（支持 boolean 或字符串 "true"/"false"） */
  hideMenu?: boolean | string;
  /** 是否为超级管理员（支持 boolean 或字符串 "true"/"false"） */
  isSuperManager?: boolean | string;
  /** 自定义 headers 数组，每项包含 headerName 和 headerValue */
  auth?: AuthHeaderItem[];
  /** 其他任意参数 */
  [key: string]: unknown;
}

/**
 * 心跳消息
 * 用于检测父窗口连接状态
 */
export interface IframeHeartbeatMessage {
  type: "HEARTBEAT";
  timestamp: number;
}

/**
 * 就绪查询消息
 * 父窗口查询子窗口是否准备就绪
 */
export interface IframeReadyRequest {
  type: "READY_REQUEST";
}

/**
 * 就绪响应消息
 * 子窗口响应父窗口的就绪查询
 */
export interface IframeReadyResponse {
  type: "READY_RESPONSE";
  initialized: boolean;
}

/**
 * 入站消息类型（父 → 子）
 */
export type IframeIncomingMessage =
  | IframeUserDataMessage
  | IframeHeartbeatMessage
  | IframeReadyRequest;

/**
 * 出站消息类型（子 → 父）
 */
export type IframeOutgoingMessage = IframeReadyResponse;

/**
 * iframe 上下文状态
 * 存储从父窗口接收的参数
 */
export interface IframeContext {
  /** 是否已初始化 */
  initialized: boolean;
  /** 用户 ID（来自 sapId） */
  userId: string | null;
  /** Claw 名称 */
  clawName: string | null;
  /** 空间标识 */
  space: string | null;
  /** 来源标识 */
  source: string | null;
  /** 是否隐藏菜单 */
  hideMenu: boolean;
  /** 是否为超级管理员 */
  isSuperManager: boolean;
  /** 自定义 headers 数组 */
  authHeaders: AuthHeaderItem[];
  /** 来源 origin */
  parentOrigin: string | null;
  /** 接收消息的时间戳 */
  receivedAt: number | null;
}