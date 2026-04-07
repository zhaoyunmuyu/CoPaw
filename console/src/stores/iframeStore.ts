/**
 * iframe 上下文状态存储
 *
 * 使用 Zustand 管理从父级 iframe 接收的参数
 * 支持持久化到 sessionStorage
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
      name: "copaw-iframe-context",
      partialize: (state) => ({
        userId: state.userId,
        clawName: state.clawName,
        space: state.space,
        source: state.source,
        hideMenu: state.hideMenu,
        isSuperManager: state.isSuperManager,
        authHeaders: state.authHeaders,
        parentOrigin: state.parentOrigin,
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