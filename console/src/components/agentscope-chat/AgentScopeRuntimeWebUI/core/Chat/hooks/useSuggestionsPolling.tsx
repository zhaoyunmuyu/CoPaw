import { useCallback, useRef, useEffect } from "react";
import { useContextSelector } from "use-context-selector";
import { ChatAnywhereSessionsContext } from "../../Context/ChatAnywhereSessionsContext";
import { useChatAnywhereOptions } from "../../Context/ChatAnywhereOptionsContext";
import { buildAuthHeaders } from "@/api/authHeaders";

/**
 * 猜你想问建议轮询 Hook
 *
 * 在响应完成后轮询获取建议，并更新到当前响应中
 */
export default function useSuggestionsPolling(options: {
  currentQARef: React.MutableRefObject<{
    request?: any;
    response?: any;
    abortController?: AbortController;
  }>;
  updateMessage: (message: any) => void;
}) {
  const { currentQARef, updateMessage } = options;

  // 前端临时 sessionId
  const currentSessionId = useContextSelector(
    ChatAnywhereSessionsContext,
    (v) => v.currentSessionId,
  );

  // 获取 session API（包含 getRealIdForSession 方法，用于后端轮询）
  const sessionApi = useChatAnywhereOptions((v) => v.session?.api);

  // 使用 ref 避免闭包陷阱
  const sessionIdRef = useRef(currentSessionId);

  // 记录当前活跃的轮询 response.id，用于取消过期轮询
  const activePollResponseIdRef = useRef<string | null>(null);

  useEffect(() => {
    sessionIdRef.current = currentSessionId;
  }, [currentSessionId]);

  /**
   * 轮询获取建议
   *
   * 在响应完成后调用，轮询最多5次，每次间隔1000ms
   * 如果后端建议功能未启用，则返回空列表，前端不显示
   */
  const pollSuggestions = useCallback(async () => {
    const sessionId = sessionIdRef.current;
    if (!sessionId) {
      console.debug("[Suggestions] No session ID available");
      return;
    }

    // 记录当前轮询对应的 response.id
    const pollResponseId = currentQARef.current.response?.id;
    if (!pollResponseId) {
      console.debug("[Suggestions] No response ID available");
      return;
    }

    // 标记当前轮询为活跃（新轮询会覆盖此值，从而取消旧轮询）
    activePollResponseIdRef.current = pollResponseId;

    // 获取真实的 session ID（UUID）用于后端轮询
    // 后端存储 suggestions 时用的是 chat.id (UUID)
    const realSessionId = (sessionApi as any)?.getRealIdForSession?.(sessionId) ?? sessionId;
    console.debug("[Suggestions] Polling with realSessionId:", realSessionId, "responseId:", pollResponseId);

    // 获取认证 headers（包含 X-Tenant-Id）
    const headers = buildAuthHeaders();

    // 使用相对路径，通过 vite proxy 转发
    const suggestionsUrl = `/api/console/suggestions`;

    // 轮询最多5次（建议生成需要约2秒，需要足够时间）
    for (let i = 0; i < 5; i++) {
      // 检查是否仍然是活跃的轮询（防止竞态：用户已发起新请求）
      if (activePollResponseIdRef.current !== pollResponseId) {
        console.debug("[Suggestions] Polling cancelled, responseId mismatch. Expected:", pollResponseId, "Active:", activePollResponseIdRef.current);
        return;
      }

      console.debug("[Suggestions] Polling attempt", i + 1, "for session:", realSessionId);
      try {
        const response = await fetch(
          `${suggestionsUrl}?session_id=${realSessionId}`,
          {
            method: "GET",
            headers,
          },
        );

        if (response.ok) {
          const data = await response.json();
          console.debug("[Suggestions] Response:", data);
          if (data.suggestions?.length > 0) {
            // 取第一个建议列表（可能有多个，但通常只有一个）
            const suggestions = data.suggestions[0]?.suggestions || [];
            if (suggestions.length > 0) {
              console.debug("[Suggestions] Got suggestions:", suggestions);

              // 再次验证 response.id 是否一致（防止轮询期间用户发起新请求）
              const currentResponse = currentQARef.current.response;
              if (currentResponse?.id !== pollResponseId) {
                console.debug("[Suggestions] Response ID mismatch, skipping update. Expected:", pollResponseId, "Current:", currentResponse?.id);
                return;
              }

              if (currentResponse?.cards?.[0]?.data) {
                // 创建新的 cards 数组，确保触发 React 重新渲染
                const updatedCards = [
                  {
                    ...currentResponse.cards[0],
                    data: {
                      ...currentResponse.cards[0].data,
                      suggestions: suggestions,
                    },
                  },
                  ...currentResponse.cards.slice(1),
                ];

                // 更新整个 response 对象，确保 React 检测到变化
                currentQARef.current.response = {
                  ...currentResponse,
                  cards: updatedCards,
                };

                updateMessage(currentQARef.current.response);
              }
              return; // 成功获取，停止轮询
            }
          }
        } else {
          console.debug("[Suggestions] Response not ok:", response.status);
        }
      } catch (error) {
        // 静默失败，继续轮询
        console.debug("[Suggestions] Polling attempt failed:", i + 1, error);
      }

      // 等待1000ms后继续轮询（建议生成需要约2秒）
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
    console.debug("[Suggestions] Polling finished, no suggestions found");
  }, [currentQARef, updateMessage, sessionApi]);

  return { pollSuggestions };
}