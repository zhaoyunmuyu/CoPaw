import { beforeEach, describe, expect, it, vi } from "vitest";
import { SessionApi } from "./index";

const apiMocks = vi.hoisted(() => ({
  listChats: vi.fn(),
  getChat: vi.fn(),
  deleteChat: vi.fn(),
}));

const cronJobApiMocks = vi.hoisted(() => ({
  listCronJobs: vi.fn(),
}));

vi.mock("../../../api", () => ({
  __esModule: true,
  default: {
    listChats: apiMocks.listChats,
    getChat: apiMocks.getChat,
    deleteChat: apiMocks.deleteChat,
  },
}));

vi.mock("../../../api/modules/cronjob", () => ({
  cronJobApi: {
    listCronJobs: cronJobApiMocks.listCronJobs,
  },
}));

vi.mock("../../../utils/identity", () => ({
  getUserId: vi.fn(() => "user-1"),
  getChannel: vi.fn(() => "console"),
  getUserIdWithoutWindow: vi.fn((value?: string) => value || "user-1"),
  getChannelWithoutWindow: vi.fn((value?: string) => value || "console"),
}));

describe("SessionApi identity mapping", () => {
  beforeEach(() => {
    apiMocks.listChats.mockReset();
    apiMocks.getChat.mockReset();
    apiMocks.deleteChat.mockReset();
    cronJobApiMocks.listCronJobs.mockReset();
    cronJobApiMocks.listCronJobs.mockResolvedValue([]);
    sessionStorage.clear();
    const runtimeWindow = window as Window & {
      currentSessionId?: string;
      currentUserId?: string;
      currentChannel?: string;
    };
    runtimeWindow.currentSessionId = undefined;
    runtimeWindow.currentUserId = undefined;
    runtimeWindow.currentChannel = undefined;
  });

  it("keeps the logical session id stable after the first reply resolves a real chat id", async () => {
    const sessionApi = new SessionApi();

    await sessionApi.createSession({
      name: "new chat",
      messages: [],
    });

    const logicalSessionId = sessionApi.getPendingSessionId();
    expect(logicalSessionId).toBeTruthy();

    const resolved = vi.fn();
    sessionApi.onSessionIdResolved = resolved;

    apiMocks.listChats.mockResolvedValue([
      {
        id: "chat-real-1",
        name: "new chat",
        session_id: logicalSessionId,
        user_id: "user-1",
        channel: "console",
        meta: {},
        status: "idle",
        created_at: "2026-04-22T00:00:00Z",
      },
    ]);

    await sessionApi.updateSession({
      id: logicalSessionId!,
      name: "new chat",
    });

    expect(resolved).toHaveBeenCalledWith(logicalSessionId, "chat-real-1");
    expect(sessionApi.getLogicalSessionId(logicalSessionId!)).toBe(
      logicalSessionId,
    );
    expect(sessionApi.getChatIdForSession(logicalSessionId!)).toBe(
      "chat-real-1",
    );
    expect(
      (window as Window & { currentSessionId?: string }).currentSessionId,
    ).toBe(logicalSessionId);
  });

  it("resolves persisted chats back to their backend chat id from the logical session id", async () => {
    const sessionApi = new SessionApi();

    apiMocks.listChats.mockResolvedValue([
      {
        id: "chat-real-1",
        name: "persisted chat",
        session_id: "channel:user-1",
        user_id: "user-1",
        channel: "console",
        meta: {},
        status: "running",
        created_at: "2026-04-22T00:00:00Z",
      },
    ]);

    await sessionApi.getSessionList();

    expect(sessionApi.getChatIdForSession("channel:user-1")).toBe(
      "chat-real-1",
    );
  });

  it("clears temp-to-real mappings when deleting the persisted backend chat", async () => {
    const sessionApi = new SessionApi();

    sessionStorage.setItem(
      "copaw_resolved_chat_ids",
      JSON.stringify({
        temp_123: "chat-real-1",
      }),
    );
    apiMocks.listChats.mockResolvedValue([
      {
        id: "chat-real-1",
        name: "persisted chat",
        session_id: "channel:user-1",
        user_id: "user-1",
        channel: "console",
        meta: {},
        status: "idle",
        created_at: "2026-04-22T00:00:00Z",
      },
    ]);
    apiMocks.deleteChat.mockResolvedValue({
      success: true,
      chat_id: "chat-real-1",
    });

    await sessionApi.getSessionList();
    await sessionApi.removeSession({ id: "chat-real-1" });

    expect(apiMocks.deleteChat).toHaveBeenCalledWith("chat-real-1");
    expect(sessionStorage.getItem("copaw_resolved_chat_ids")).toBe("{}");
  });
});
