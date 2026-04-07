import { getApiToken } from "./config";
import { getIframeContext } from "../stores/iframeStore";

/**
 * 构建认证和上下文相关的请求 headers
 *
 * 包含：
 * - Authorization: Bearer token
 * - X-Agent-Id: 当前选中的 agent
 * - X-User-Id: 用户 ID（来自 iframe userId，默认 "default"）
 * - X-Tenant-Id: 租户 ID（与 X-User-Id 保持一致）
 * - 自定义 headers（来自 iframe auth 数组）
 */
export function buildAuthHeaders(): Record<string, string> {
  const headers: Record<string, string> = {};

  // 1. Token（优先级：localStorage > iframe context）
  const token = getApiToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  // 2. Agent ID（从 sessionStorage 读取当前选中的 agent）
  try {
    const agentStorage = sessionStorage.getItem("copaw-agent-storage");
    if (agentStorage) {
      const parsed = JSON.parse(agentStorage);
      const selectedAgent = parsed?.state?.selectedAgent;
      if (selectedAgent) {
        headers["X-Agent-Id"] = selectedAgent;
      }
    }
  } catch (error) {
    console.warn("Failed to get selected agent from storage:", error);
  }

  // 3. iframe 上下文参数（从父级 iframe 接收的参数）
  const iframeContext = getIframeContext();

  // 用户 ID（默认值为 "default"）
  const userId = iframeContext.userId || "default";
  headers["X-User-Id"] = userId;
  headers["X-Tenant-Id"] = userId;

  // 4. 自定义 headers 数组（循环设置）
  if (iframeContext.authHeaders?.length) {
    for (const item of iframeContext.authHeaders) {
      if (item.headerName && item.headerValue !== undefined) {
        headers[item.headerName] = item.headerValue;
      }
    }
  }

  return headers;
}
