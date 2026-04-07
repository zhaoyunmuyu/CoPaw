import { getApiToken } from "./config";

// ==================== userId 统一整改 (Kun He) ====================
// 使用统一的 getUserId helper，遵循优先级：iframe > window > session > default
import { getUserId } from "../utils/identity";
import { getIframeContext } from "../stores/iframeStore";
// ==================== userId 统一整改结束 ====================

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

  // 3. 用户 ID 和租户 ID
  // ==================== userId 统一整改 (Kun He) ====================
  // 使用统一的 getUserId() 获取用户 ID
  // 优先级：iframe userId > window.currentUserId > DEFAULT_USER_ID
  // X-Tenant-Id 与 X-User-Id 保持一致
  const userId = getUserId();
  headers["X-User-Id"] = userId;
  headers["X-Tenant-Id"] = userId;

  // 4. 自定义 headers 数组（父窗口通过 auth 字段传递）
  // 注意：排除 X-User-Id，因为已由 getUserId() 处理
  const iframeContext = getIframeContext();
  if (iframeContext.authHeaders?.length) {
    for (const item of iframeContext.authHeaders) {
      // 跳过 X-User-Id，避免覆盖上面设置的值
      if (
        item.headerName &&
        item.headerValue !== undefined &&
        item.headerName !== "X-User-Id"
      ) {
        headers[item.headerName] = item.headerValue;
      }
    }
  }
  // ==================== userId 统一整改结束 ====================

  return headers;
}
