import { beforeEach, describe, expect, it } from "vitest";
import {
  getInitialSessionId,
  getInitialSessionSelection,
} from "./initialSessionSelection";

describe("getInitialSessionId", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("restores the resolved backend chat id when the URL still contains a stale temporary id", () => {
    sessionStorage.setItem(
      "copaw_resolved_chat_ids",
      JSON.stringify({
        temp_123: "chat-real-123",
      }),
    );

    expect(
      getInitialSessionId({
        pathname: "/chat/temp_123",
        sessionList: [
          {
            id: "chat-real-123",
            name: "resolved chat",
            messages: [],
          },
        ],
      }),
    ).toBe("chat-real-123");
  });

  it("ignores a stale resolved mapping when the backend chat is no longer in the session list", () => {
    sessionStorage.setItem(
      "copaw_resolved_chat_ids",
      JSON.stringify({
        temp_123: "chat-real-123",
      }),
    );

    expect(
      getInitialSessionId({
        pathname: "/chat/temp_123",
        sessionList: [],
      }),
    ).toBeUndefined();
    expect(sessionStorage.getItem("copaw_resolved_chat_ids")).toBe("{}");
  });

  it("resolves a logical session id deep link to the newest persisted chat", () => {
    expect(
      getInitialSessionId({
        pathname: "/chat/channel:user-1",
        sessionList: [
          {
            id: "chat-real-older",
            name: "older chat",
            messages: [],
            sessionId: "channel:user-1",
            createdAt: "2026-04-21T00:00:00Z",
          } as any,
          {
            id: "chat-real-newer",
            name: "newer chat",
            messages: [],
            sessionId: "channel:user-1",
            createdAt: "2026-04-22T00:00:00Z",
          } as any,
        ],
      }),
    ).toBe("chat-real-newer");
  });

  it("returns the canonical backend chat id for logical session deep links", () => {
    expect(
      getInitialSessionSelection({
        pathname: "/chat/channel:user-1",
        sessionList: [
          {
            id: "chat-real-older",
            name: "older chat",
            messages: [],
            sessionId: "channel:user-1",
            createdAt: "2026-04-21T00:00:00Z",
          } as any,
          {
            id: "chat-real-newer",
            name: "newer chat",
            messages: [],
            sessionId: "channel:user-1",
            createdAt: "2026-04-22T00:00:00Z",
          } as any,
        ],
      }),
    ).toEqual({
      requestedSessionId: "channel:user-1",
      resolvedSessionId: "chat-real-newer",
    });
  });
});
