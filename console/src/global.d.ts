/**
 * ============================================================
 * Author: Kun He
 * Description: 全局类型定义
 * Date: 2026-04-07
 * ============================================================
 */
declare global {
  interface Window {
    __env__?: {
      baseUrl?: string;
    };
  }
}

// iframe postMessage 通信类型导出
// 使其他模块可以直接从 global.d.ts 导入类型
export type { AuthHeaderItem, IframeContext } from "./types/iframe";