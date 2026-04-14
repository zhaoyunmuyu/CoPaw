/**
 * ============================================================
 * iframe 上下文状态存储
 * Author: Kun He
 * Date: 2026-04-07
 * ============================================================
 *
 * 使用 Zustand 管理从父级 iframe 接收的参数
 * 支持持久化到 sessionStorage
 *
 * 存储字段：
 * - userId: 用户 ID（来自父窗口的 sapId 参数）
 * - clawName: Claw 名称
 * - space: 空间标识
 * - source: 来源标识
 * - hideMenu: 是否隐藏菜单
 * - isSuperManager: 是否为超级管理员
 * - authHeaders: 自定义 headers 数组
 * - parentOrigin: 父窗口来源 origin
 *
 * 相关文件：
 * - types/iframe.ts: 类型定义
 * - utils/iframeMessage.ts: 消息处理逻辑
 * ============================================================
 */
import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { IframeContext, AuthHeaderItem } from "../types/iframe";

interface IframeStore extends IframeContext {
  /**
   * 设置 iframe 上下文
   * @param context - 部分上下文参数
   */
  setContext: (
    context: Partial<Omit<IframeContext, "initialized" | "receivedAt">>,
  ) => void;

  /**
   * 标记初始化完成
   */
  markInitialized: () => void;

  /**
   * 清除所有上下文
   */
  clearContext: () => void;

  /**
   * 设置自定义 headers
   * @param authHeaders - 自定义 header 数组
   */
  setAuthHeaders: (authHeaders: AuthHeaderItem[]) => void;
}

/** 初始状态 */
const initialState: IframeContext = {
  initialized: false,
  userId: null,
  clawName: null,
  space: null,
  source: null,
  hideMenu: false,
  isSuperManager: false,
  authHeaders: [],
  parentOrigin: null,
  receivedAt: null,
  sysId: null,
  token: null,
  bbk: null,
  orgCode: null,
  orgLvl: null,
  positionId: null,
  userChange: false,
};

export const useIframeStore = create<IframeStore>()(
  persist(
    (set) => ({
      ...initialState,

      setContext: (context) =>
        set((state) => ({
          ...state,
          ...context,
          receivedAt: Date.now(),
        })),

      markInitialized: () => set({ initialized: true }),

      clearContext: () => set(initialState),

      setAuthHeaders: (authHeaders) => set({ authHeaders }),
    }),
    {
      name: "swe-iframe-context",
      partialize: (state) => ({
        userId: state.userId,
        clawName: state.clawName,
        space: state.space,
        source: state.source,
        hideMenu: state.hideMenu,
        isSuperManager: state.isSuperManager,
        authHeaders: state.authHeaders,
        parentOrigin: state.parentOrigin,
        sysId: state.sysId,
        token: state.token,
        bbk: state.bbk,
        orgCode: state.orgCode,
        orgLvl: state.orgLvl,
        positionId: state.positionId,
        userChange: state.userChange,
      }),
      storage: {
        getItem: (name) => {
          try {
            const value = sessionStorage.getItem(name);
            return value ? JSON.parse(value) : null;
          } catch {
            return null;
          }
        },
        setItem: (name, value) => {
          try {
            sessionStorage.setItem(name, JSON.stringify(value));
          } catch {
            // ignore storage errors
          }
        },
        removeItem: (name) => {
          sessionStorage.removeItem(name);
        },
      },
    },
  ),
);

/**
 * 非 React 组件获取 iframe 上下文的辅助函数
 * @returns 当前 iframe 上下文状态
 */
export function getIframeContext(): IframeContext {
  return useIframeStore.getState();
}