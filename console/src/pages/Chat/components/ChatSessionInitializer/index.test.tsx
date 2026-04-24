import React from "react";
import { render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ChatSessionInitializer from ".";

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  setCurrentSessionId: vi.fn(),
  setSelectedAgent: vi.fn(),
  sessions: [
    {
      id: "chat-2",
      name: "other chat",
      messages: [],
      meta: { agent_id: "agent-b" },
    },
  ],
  currentSessionId: "chat-1",
  pathname: "/chat/chat-2",
  selectedAgent: "agent-a",
}));

vi.mock("react-router-dom", () => ({
  useLocation: () => ({ pathname: mocks.pathname }),
  useNavigate: () => mocks.navigate,
}));

vi.mock("@/components/agentscope-chat", () => ({
  useChatAnywhereSessionsState: () => ({
    sessions: mocks.sessions,
    currentSessionId: mocks.currentSessionId,
    setCurrentSessionId: mocks.setCurrentSessionId,
  }),
}));

vi.mock("@/stores/agentStore", () => ({
  useAgentStore: (selector?: (value: unknown) => unknown) => {
    const store = {
      selectedAgent: mocks.selectedAgent,
      setSelectedAgent: mocks.setSelectedAgent,
    };
    return selector ? selector(store) : store;
  },
}));

describe("ChatSessionInitializer", () => {
  beforeEach(() => {
    mocks.navigate.mockReset();
    mocks.setCurrentSessionId.mockReset();
    mocks.setSelectedAgent.mockReset();
    mocks.sessions = [
      {
        id: "chat-2",
        name: "other chat",
        messages: [],
        meta: { agent_id: "agent-b" },
      },
    ];
    mocks.currentSessionId = "chat-1";
    mocks.pathname = "/chat/chat-2";
    mocks.selectedAgent = "agent-a";
  });

  it("aligns the selected agent before loading a session bound to another agent", () => {
    render(<ChatSessionInitializer />);

    expect(mocks.setSelectedAgent).toHaveBeenCalledWith("agent-b");
    expect(mocks.setCurrentSessionId).toHaveBeenCalledWith("chat-2");
    expect(mocks.navigate).not.toHaveBeenCalled();
  });
});
