import { sleep, Stream } from "@/components/agentscope-chat";
import { useCallback, useRef, useEffect } from "react";
import { useChatAnywhereOptions } from "../../Context/ChatAnywhereOptionsContext";
import AgentScopeRuntimeResponseBuilder from "../../AgentScopeRuntime/Response/Builder";
import {
  AgentScopeRuntimeRunStatus,
  AgentScopeRuntimeMessageType,
} from "../../AgentScopeRuntime/types";
import { IAgentScopeRuntimeWebUIMessage } from "@/components/agentscope-chat";
import { IAgentScopeRuntimeWebUIInputData } from "../../types";
import { withResponseHeaderMeta } from "./headerMeta";
import type { CurrentQARef } from "./currentQARef";

interface UseChatRequestOptions {
  currentQARef: CurrentQARef;
  updateMessage: (message: IAgentScopeRuntimeWebUIMessage) => void;
  getCurrentSessionId: () => string;
  onFinish: () => void;
}

/**
 * 处理 API 请求和流式响应的 Hook
 */
export default function useChatRequest(options: UseChatRequestOptions) {
  const { currentQARef, updateMessage, getCurrentSessionId, onFinish } =
    options;
  const apiOptions = useChatAnywhereOptions((v) => v.api);

  // 使用 ref 保存最新的 apiOptions，避免闭包陷阱
  const apiOptionsRef = useRef(apiOptions);

  useEffect(() => {
    apiOptionsRef.current = apiOptions;
  }, [apiOptions]);

  const getResponseHeaderTimestamp = useCallback(() => {
    return (
      currentQARef.current.response?.cards?.[0]?.data?.headerMeta?.timestamp ??
      currentQARef.current.response?.liveHeaderTimestamp
    );
  }, [currentQARef]);

  const mockRequest = useCallback(async (mockdata) => {
    const responseHeaderTimestamp = getResponseHeaderTimestamp();
    const agentScopeRuntimeResponseBuilder =
      new AgentScopeRuntimeResponseBuilder({
        id: "",
        status: AgentScopeRuntimeRunStatus.Created,
        created_at: 0,
      });

    for await (const chunk of mockdata) {
      const res = agentScopeRuntimeResponseBuilder.handle(chunk);
      currentQARef.current.response.cards = [
        {
          code: "AgentScopeRuntimeResponseCard",
          data: withResponseHeaderMeta(res, responseHeaderTimestamp),
        },
      ];

      updateMessage(currentQARef.current.response);

      await sleep(100);
    }
  }, []);

  const processSSEResponse = useCallback(
    async (response: Response) => {
      const responseHeaderTimestamp = getResponseHeaderTimestamp();
      const buildResponseCard = () => {
        const responseData = currentQARef.current.response?.cards?.[0]
          ?.data as
          | {
              id?: string;
              status?: AgentScopeRuntimeRunStatus;
              created_at?: number;
              output?: unknown[];
            }
          | undefined;

        const builder = new AgentScopeRuntimeResponseBuilder({
          id: responseData?.id || "",
          status: responseData?.status || AgentScopeRuntimeRunStatus.Created,
          created_at: responseData?.created_at || 0,
        });

        if (responseData) {
          builder.handle(responseData as never);
        }

        return builder;
      };

      const cancelActiveRequest = async () => {
        currentQARef.current.abortController?.abort();

        const currentApiOptions = apiOptionsRef.current;
        if (currentApiOptions.cancel) {
          await Promise.resolve(
            currentApiOptions.cancel({
              session_id: getCurrentSessionId(),
            }),
          ).catch((error) => {
            console.error(error);
          });
        }

        if (currentQARef.current.response) {
          currentQARef.current.response.cards = [
            {
              code: "AgentScopeRuntimeResponseCard",
              data: withResponseHeaderMeta(
                buildResponseCard().cancel(),
                responseHeaderTimestamp,
              ),
            },
          ];

          updateMessage(currentQARef.current.response);
        }
      };

      const agentScopeRuntimeResponseBuilder = buildResponseCard();

      if (!response.ok) {
        response.json().then((data) => {
          const res = agentScopeRuntimeResponseBuilder.handle({
            object: "message",
            type: AgentScopeRuntimeMessageType.ERROR,
            content: [],
            id: "error",
            role: "assistant",
            status: AgentScopeRuntimeRunStatus.Failed,
            code: String(response.status),
            message: JSON.stringify(data),
          });

          currentQARef.current.response.cards = [
            {
              code: "AgentScopeRuntimeResponseCard",
              data: withResponseHeaderMeta(res, responseHeaderTimestamp),
            },
          ];
          onFinish();
        });
        return;
      }

      try {
        for await (const chunk of Stream({
          readableStream: response.body,
        })) {
          if (currentQARef.current.response?.msgStatus === "interrupted") {
            await cancelActiveRequest();
            break;
          }

          const responseParser =
            apiOptionsRef.current.responseParser || JSON.parse;
          const chunkData = responseParser(chunk.data);
          const res = agentScopeRuntimeResponseBuilder.handle(chunkData);

          if (
            res.status !== AgentScopeRuntimeRunStatus.Failed &&
            !res.output?.[0]?.content?.length
          )
            continue;

          if (currentQARef.current.response) {
            currentQARef.current.response.cards = [
              {
                code: "AgentScopeRuntimeResponseCard",
                data: withResponseHeaderMeta(res, responseHeaderTimestamp),
              },
            ];

            if (
              res.status === AgentScopeRuntimeRunStatus.Completed ||
              res.status === AgentScopeRuntimeRunStatus.Failed
            ) {
              onFinish();
            } else {
              updateMessage(currentQARef.current.response);
            }
          }
        }
      } catch (error) {
        console.error(error);
      }
    },
    [getCurrentSessionId, currentQARef, getResponseHeaderTimestamp, updateMessage, onFinish],
  );

  const request = useCallback(
    async (
      historyMessages: any[],
      biz_params?: IAgentScopeRuntimeWebUIInputData["biz_params"],
    ) => {
      const currentApiOptions = apiOptionsRef.current;
      const { enableHistoryMessages = false } = currentApiOptions;
      const abortSignal = currentQARef.current.abortController?.signal;
      let response;
      try {
        response = currentApiOptions.fetch
          ? await currentApiOptions.fetch({
              input: historyMessages,
              biz_params,
              signal: abortSignal,
            })
          : await fetch(currentApiOptions.baseURL, {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${currentApiOptions.token || ""}`,
              },
              body: JSON.stringify({
                input: enableHistoryMessages
                  ? historyMessages
                  : historyMessages.slice(-1),
                session_id: getCurrentSessionId(),
                stream: true,
                biz_params,
              }),
              signal: abortSignal,
            });
      } catch (error) {}

      if (response && response.body) {
        await processSSEResponse(response);
      }
    },
    [getCurrentSessionId, currentQARef, processSSEResponse],
  );

  const reconnect = useCallback(
    async (sessionId: string) => {
      const currentApiOptions = apiOptionsRef.current;
      if (!currentApiOptions.reconnect) return;

      const abortSignal = currentQARef.current.abortController?.signal;
      let response: Response | undefined;
      try {
        response = await currentApiOptions.reconnect({
          session_id: sessionId,
          signal: abortSignal,
        });
      } catch (error) {}

      if (response && response.body) {
        await processSSEResponse(response);
      }
    },
    [currentQARef, processSSEResponse],
  );

  const cancelActiveRequest = useCallback(async () => {
    const responseHeaderTimestamp = getResponseHeaderTimestamp();
    const responseData = currentQARef.current.response?.cards?.[0]?.data as
      | {
          id?: string;
          status?: AgentScopeRuntimeRunStatus;
          created_at?: number;
        }
      | undefined;
    const responseBuilder = new AgentScopeRuntimeResponseBuilder({
      id: responseData?.id || "",
      status: responseData?.status || AgentScopeRuntimeRunStatus.Created,
      created_at: responseData?.created_at || 0,
    });

    if (responseData) {
      responseBuilder.handle(responseData as never);
    }

    currentQARef.current.abortController?.abort();

    const currentApiOptions = apiOptionsRef.current;
    if (currentApiOptions.cancel) {
      await Promise.resolve(
        currentApiOptions.cancel({
          session_id: getCurrentSessionId(),
        }),
      ).catch((error) => {
        console.error(error);
      });
    }

    if (currentQARef.current.response) {
      currentQARef.current.response.cards = [
        {
          code: "AgentScopeRuntimeResponseCard",
          data: withResponseHeaderMeta(
            responseBuilder.cancel(),
            responseHeaderTimestamp,
          ),
        },
      ];

      updateMessage(currentQARef.current.response);
    }
  }, [currentQARef, getCurrentSessionId, getResponseHeaderTimestamp, updateMessage]);

  return { request, reconnect, mockRequest, cancelActiveRequest };
}
