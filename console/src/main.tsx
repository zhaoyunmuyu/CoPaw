import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import "./i18n";

// ==================== iframe 集成 (Kun He) ====================
// 在 React 渲染之前尽早初始化 iframe 消息监听器
// 确保不遗漏父窗口发送的任何初始化消息 (USER_DATA)
import { initIframeMessageListener } from "./utils/iframeMessage";
// ==================== iframe 集成结束 ====================

if (typeof window !== "undefined") {
  // ==================== iframe 集成 (Kun He) ====================
  // 尽早初始化 iframe 消息监听器（在 React 渲染之前）
  // 确保不遗漏父窗口发送的任何消息
  initIframeMessageListener();
  // ==================== iframe 集成结束 ====================

  const originalError = console.error;
  const originalWarn = console.warn;

  console.error = function (...args: any[]) {
    const msg = args[0]?.toString() || "";
    if (msg.includes(":first-child") || msg.includes("pseudo class")) {
      return;
    }
    originalError.apply(console, args);
  };

  console.warn = function (...args: any[]) {
    const msg = args[0]?.toString() || "";
    if (
      msg.includes(":first-child") ||
      msg.includes("pseudo class") ||
      msg.includes("potentially unsafe")
    ) {
      return;
    }
    originalWarn.apply(console, args);
  };
}

createRoot(document.getElementById("root")!).render(<App />);
