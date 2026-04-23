import React from "react";
import { act, render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import useChatRequest from "./useChatRequest";
import type { CurrentQARef } from "./currentQARef";
import type { ChatRequestOwner } from "./requestOwnership";

const mocks = vi.hoisted(() => {
  const streamGate = {
    promise: Promise.resolve(),
    resolve: () => {},
  };

  return {
    fetch: vi.fn(),
    cancel: vi.fn(),
    streamGate,
  };
});

vi.mock("@/components/agentscope-chat", () => ({
  sleep: vi.fn(async () => {}),
  uuid: vi.fn(() => "uuid-1"),
  Stream: vi.fn(() => ({
    async *[Symbol.asyncIterator]() {
      yield {
        data: JSON.stringify({
          object: "response",
          id: "response-1",
          status: "in_progress",
          created_at: 1,
          output: [
            {
              object: "message",
              id: "message-1",
              role: "assistant",
              type: "message",
              status: "in_progress",
              content: [
                {
                  object: "content",
                  type: "text",
                  text: "hello",
                  status: "completed",
                },
              ],
            },
          ],
        }),
      };

      await mocks.streamGate.promise;

      yield {
        data: JSON.stringify({
          object: "response",
          id: "response-1",
          status: "completed",
          created_at: 1,
          completed_at: 2,
          output: [
            {
              object: "message",
              id: "message-1",
              role: "assistant",
              type: "message",
              status: "completed",
              content: [
                {
                  object: "content",
                  type: "text",
                  text: "hello world",
                  status: "completed",
                },
              ],
            },
          ],
        }),
      };
    },
  })),
}));

vi.mock("../../Context/ChatAnywhereOptionsContext", () => ({
  useChatAnywhereOptions: (selector: (value: unknown) => unknown) =>
    selector({
      api: {
        fetch: mocks.fetch,
        cancel: mocks.cancel,
        responseParser: JSON.parse,
      },
    }),
}));

let hookApi: ReturnType<typeof useChatRequest>;

function createOwner(
  overrides: Partial<ChatRequestOwner> = {},
): ChatRequestOwner {
  return {
    requestId: "request-1",
    kind: "submit",
    sessionId: "chat-a",
    logicalSessionId: "logical-a",
    chatId: "chat-real-a",
    ...overrides,
  };
}

function Harness(props: {
  currentQARef: CurrentQARef;
  updateMessage: (message: unknown) => void;
  onFinish: (owner: ChatRequestOwner) => void;
}) {
  hookApi = useChatRequest({
    currentQARef: props.currentQARef,
    updateMessage: props.updateMessage,
    getCurrentSessionId: () => "chat-b",
    onFinish: props.onFinish,
  });

  return null;
}

describe("useChatRequest", () => {
  beforeEach(() => {
    mocks.fetch.mockReset();
    mocks.cancel.mockReset();
    let resolveGate: () => void = () => {};
    mocks.streamGate.promise = new Promise<void>((resolve) => {
      resolveGate = resolve;
    });
    mocks.streamGate.resolve = resolveGate;
  });

  it("ignores delayed SSE chunks after another request owns the active response", async () => {
    mocks.fetch.mockResolvedValue({
      ok: true,
      body: {},
    } as Response);

    const updateMessage = vi.fn();
    const onFinish = vi.fn();
    const currentQARef = {
      current: {
        response: {
          id: "ui-response-a",
          msgStatus: "generating",
          cards: [
            {
              code: "AgentScopeRuntimeResponseCard",
              data: {
                id: "response-1",
                status: "created",
                created_at: 0,
                output: [],
              },
            },
          ],
        },
        activeRequestOwner: createOwner(),
      },
    } as CurrentQARef;

    render(
      <Harness
        currentQARef={currentQARef}
        updateMessage={updateMessage}
        onFinish={onFinish}
      />,
    );

    const requestPromise = hookApi.request([], undefined, createOwner());

    await waitFor(() => {
      expect(updateMessage).toHaveBeenCalledTimes(1);
    });

    currentQARef.current.activeRequestOwner = createOwner({
      requestId: "request-2",
      sessionId: "chat-b",
      logicalSessionId: "logical-b",
      chatId: "chat-real-b",
    });
    currentQARef.current.response = {
      id: "ui-response-b",
      role: "assistant",
      msgStatus: "generating",
      cards: [
        {
          code: "AgentScopeRuntimeResponseCard",
          data: {
            id: "response-2",
            status: "created",
            created_at: 0,
            output: [],
          },
        },
      ],
    };

    mocks.streamGate.resolve();

    await act(async () => {
      await requestPromise;
    });

    expect(updateMessage).toHaveBeenCalledTimes(1);
    expect(onFinish).not.toHaveBeenCalled();
  });
});
