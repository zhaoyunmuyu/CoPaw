import { beforeEach, describe, expect, it } from "vitest";
import { getInitialSessionId } from "./initialSessionSelection";

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
});
