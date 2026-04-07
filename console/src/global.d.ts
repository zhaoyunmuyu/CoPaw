declare global {
  interface Window {
    __env__?: {
      baseUrl?: string;
    };
  }
}

// iframe postMessage 通信类型导出
export type { AuthHeaderItem, IframeContext } from "./types/iframe";
