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
    apiMocks.getChat.mockResolvedValue({
      id: "chat-real-1",
      status: "running",
      messages: [],
    });

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

  it("shows a pending local session in the history list immediately after creation", async () => {
    const sessionApi = new SessionApi();

    const list = await sessionApi.createSession({
      name: "new chat",
      messages: [],
    });

    const logicalSessionId = sessionApi.getPendingSessionId();
    expect(logicalSessionId).toBeTruthy();
    expect(list).toHaveLength(1);
    expect(list[0]?.id).toBe(logicalSessionId);
    expect(list[0]?.name).toBe("new chat");
  });

  it("keeps multiple pending local sessions when backend persistence has not caught up yet", async () => {
    const sessionApi = new SessionApi();

    await sessionApi.createSession({
      name: "chat A",
      messages: [],
    });
    const firstSessionId = sessionApi.getPendingSessionId();

    await sessionApi.createSession({
      name: "chat B",
      messages: [],
    });
    const secondSessionId = sessionApi.getPendingSessionId();

    expect(firstSessionId).toBeTruthy();
    expect(secondSessionId).toBeTruthy();
    expect(secondSessionId).not.toBe(firstSessionId);

    apiMocks.listChats.mockResolvedValue([]);

    const list = await sessionApi.getSessionList();

    expect(list.map((session) => session.id)).toEqual(
      expect.arrayContaining([firstSessionId, secondSessionId]),
    );
  });

  it("only notifies resolution for the active pending session when multiple local sessions resolve together", async () => {
    const sessionApi = new SessionApi();

    await sessionApi.createSession({
      name: "chat A",
      messages: [],
    });
    const firstSessionId = sessionApi.getPendingSessionId();

    await sessionApi.createSession({
      name: "chat B",
      messages: [],
    });
    const secondSessionId = sessionApi.getPendingSessionId();

    expect(firstSessionId).toBeTruthy();
    expect(secondSessionId).toBeTruthy();
    expect(secondSessionId).not.toBe(firstSessionId);

    const runtimeWindow = window as Window & {
      currentSessionId?: string;
    };
    runtimeWindow.currentSessionId = secondSessionId!;

    const resolved = vi.fn();
    sessionApi.onSessionIdResolved = resolved;

    apiMocks.listChats.mockResolvedValue([
      {
        id: "chat-real-a",
        name: "chat A",
        session_id: firstSessionId,
        user_id: "user-1",
        channel: "console",
        meta: {},
        status: "idle",
        created_at: "2026-04-22T00:00:00Z",
      },
      {
        id: "chat-real-b",
        name: "chat B",
        session_id: secondSessionId,
        user_id: "user-1",
        channel: "console",
        meta: {},
        status: "idle",
        created_at: "2026-04-22T00:00:01Z",
      },
    ]);

    await sessionApi.getSessionList();

    expect(resolved).toHaveBeenCalledTimes(1);
    expect(resolved).toHaveBeenCalledWith(secondSessionId, "chat-real-b");
    expect(sessionApi.getChatIdForSession(firstSessionId!)).toBe("chat-real-a");
    expect(sessionApi.getChatIdForSession(secondSessionId!)).toBe(
      "chat-real-b",
    );
  });

  it("keeps pending session messages accessible before backend persistence catches up", async () => {
    const sessionApi = new SessionApi();

    await sessionApi.createSession({
      name: "new chat",
      messages: [],
    });

    const logicalSessionId = sessionApi.getPendingSessionId();
    const localMessages = [
      {
        id: "user-msg-1",
        role: "user" as const,
        cards: [],
      },
    ];

    apiMocks.listChats.mockResolvedValue([]);

    await sessionApi.updateSession({
      id: logicalSessionId!,
      messages: localMessages,
    });

    const session = await sessionApi.getSession(logicalSessionId!);
    const list = await sessionApi.getSessionList();

    expect(session.messages).toEqual(localMessages);
    expect(list.some((item) => item.id === logicalSessionId)).toBe(true);
  });

  it("preserves local pending messages when the backend chat id resolves before the first frame", async () => {
    const sessionApi = new SessionApi();

    await sessionApi.createSession({
      name: "new chat",
      messages: [],
    });

    const logicalSessionId = sessionApi.getPendingSessionId();
    const localMessages = [
      {
        id: "user-msg-1",
        role: "user" as const,
        cards: [],
      },
    ];

    apiMocks.listChats.mockResolvedValue([
      {
        id: "chat-real-1",
        name: "new chat",
        session_id: logicalSessionId,
        user_id: "user-1",
        channel: "console",
        meta: {},
        status: "running",
        created_at: "2026-04-22T00:00:00Z",
      },
    ]);
    apiMocks.getChat.mockResolvedValue({
      id: "chat-real-1",
      status: "running",
      messages: [],
    });

    await sessionApi.updateSession({
      id: logicalSessionId!,
      messages: localMessages,
      generating: true,
    });

    const session = await sessionApi.getSession(logicalSessionId!);
    const list = await sessionApi.getSessionList();

    expect(session.messages).toEqual(localMessages);
    expect(session.generating).toBe(true);
    expect(list[0]?.id).toBe(logicalSessionId);
    expect(list[0]?.messages).toEqual(localMessages);
    expect(list[0]?.generating).toBe(true);
  });

  it("refreshes backend state before returning an unresolved local timestamp session", async () => {
    const sessionApi = new SessionApi();

    await sessionApi.createSession({
      name: "new chat",
      messages: [],
    });

    const logicalSessionId = sessionApi.getPendingSessionId();
    expect(logicalSessionId).toBeTruthy();

    apiMocks.listChats.mockResolvedValue([
      {
        id: "chat-real-1",
        name: "new chat",
        session_id: logicalSessionId,
        user_id: "user-1",
        channel: "console",
        meta: {},
        status: "running",
        created_at: "2026-04-22T00:00:00Z",
      },
    ]);
    apiMocks.getChat.mockResolvedValue({
      id: "chat-real-1",
      status: "running",
      messages: [],
    });

    const session = await sessionApi.getSession(logicalSessionId!);

    expect(apiMocks.listChats).toHaveBeenCalled();
    expect(apiMocks.getChat).toHaveBeenCalledWith("chat-real-1");
    expect(session.generating).toBe(true);
    expect(sessionApi.getChatIdForSession(logicalSessionId!)).toBe(
      "chat-real-1",
    );
  });

  it("clears stale local generating when the resolved backend chat is idle", async () => {
    const sessionApi = new SessionApi();

    await sessionApi.createSession({
      name: "new chat",
      messages: [],
    });

    const logicalSessionId = sessionApi.getPendingSessionId();
    const localMessages = [
      {
        id: "user-msg-1",
        role: "user" as const,
        cards: [],
      },
    ];

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
    apiMocks.getChat.mockResolvedValue({
      id: "chat-real-1",
      status: "idle",
      messages: [],
    });

    await sessionApi.updateSession({
      id: logicalSessionId!,
      messages: localMessages,
      generating: true,
    });

    const session = await sessionApi.getSession(logicalSessionId!);

    expect(session.messages).toEqual(localMessages);
    expect(session.generating).toBe(false);
  });

  it("patches the last user message back into a resolved running session when backend history only has partial assistant output", async () => {
    const sessionApi = new SessionApi();

    await sessionApi.createSession({
      name: "new chat",
      messages: [],
    });

    const logicalSessionId = sessionApi.getPendingSessionId();
    expect(logicalSessionId).toBeTruthy();

    sessionApi.setLastUserMessage(logicalSessionId!, "hello from user");

    apiMocks.listChats.mockResolvedValue([
      {
        id: "chat-real-1",
        name: "new chat",
        session_id: logicalSessionId,
        user_id: "user-1",
        channel: "console",
        meta: {},
        status: "running",
        created_at: "2026-04-22T00:00:00Z",
      },
    ]);
    apiMocks.getChat.mockResolvedValue({
      id: "chat-real-1",
      status: "running",
      messages: [
        {
          id: "assistant-msg-1",
          role: "assistant",
          type: "message",
          content: [{ type: "text", text: "partial reply" }],
          timestamp: "2026-04-22T00:00:01Z",
          metadata: {},
        },
      ],
    });

    await sessionApi.updateSession({
      id: logicalSessionId!,
      name: "new chat",
      generating: true,
    });

    const session = await sessionApi.getSession(logicalSessionId!);

    expect(session.generating).toBe(true);
    expect(session.messages).toHaveLength(2);
    expect(session.messages[0]).toMatchObject({
      role: "assistant",
    });
    expect(session.messages[1]).toMatchObject({
      role: "user",
      cards: [
        {
          code: "AgentScopeRuntimeRequestCard",
          data: {
            input: [
              {
                role: "user",
                content: [{ type: "text", text: "hello from user" }],
              },
            ],
          },
        },
      ],
    });
  });

  it("does not treat a persisted logical session id as a unique backend chat id", async () => {
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

    expect(sessionApi.getChatIdForSession("channel:user-1")).toBeNull();
  });

  it("resolves a persisted local timestamp session id to its backend chat id", async () => {
    const sessionApi = new SessionApi();

    apiMocks.listChats.mockResolvedValue([
      {
        id: "3ec62b2e-c427-4778-bbab-f56188c602c4",
        name: "running chat",
        session_id: "1777001065201000",
        user_id: "user-1",
        channel: "console",
        meta: {},
        status: "running",
        created_at: "2026-04-22T00:00:00Z",
      },
    ]);

    await sessionApi.getSessionList();

    expect(sessionApi.getChatIdForSession("1777001065201000")).toBe(
      "3ec62b2e-c427-4778-bbab-f56188c602c4",
    );
  });

  it("does not resolve a logical session id to the first persisted chat when multiple chats share it", async () => {
    const sessionApi = new SessionApi();

    apiMocks.listChats.mockResolvedValue([
      {
        id: "chat-real-1",
        name: "older chat",
        session_id: "channel:user-1",
        user_id: "user-1",
        channel: "console",
        meta: {},
        status: "idle",
        created_at: "2026-04-21T00:00:00Z",
      },
      {
        id: "chat-real-2",
        name: "newer chat",
        session_id: "channel:user-1",
        user_id: "user-1",
        channel: "console",
        meta: {},
        status: "running",
        created_at: "2026-04-22T00:00:00Z",
      },
    ]);

    await sessionApi.getSessionList();

    expect(sessionApi.getChatIdForSession("channel:user-1")).toBeNull();
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
