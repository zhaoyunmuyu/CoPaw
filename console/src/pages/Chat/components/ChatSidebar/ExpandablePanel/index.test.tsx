import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ExpandablePanel from ".";

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  setSessionLoading: vi.fn(),
}));

vi.mock("react-router-dom", () => ({
  useNavigate: () => mocks.navigate,
}));

vi.mock("@/components/agentscope-chat", () => ({
  useChatAnywhereSessionsState: () => ({
    currentSessionId: "chat-1",
    setSessionLoading: mocks.setSessionLoading,
  }),
}));

describe("ExpandablePanel history", () => {
  beforeEach(() => {
    mocks.navigate.mockReset();
    mocks.setSessionLoading.mockReset();
  });

  it("ignores clicks on the already active session", () => {
    const onClose = vi.fn();

    render(
      <ExpandablePanel
        visible
        type="history"
        onClose={onClose}
        tasks={[]}
        sessions={[
          {
            id: "chat-1",
            name: "current chat",
            messages: [],
          },
        ]}
        onTaskClick={vi.fn()}
        toolbarRef={{ current: document.createElement("div") }}
      />,
    );

    fireEvent.click(screen.getByText("current chat"));

    expect(mocks.setSessionLoading).not.toHaveBeenCalled();
    expect(mocks.navigate).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("ignores clicks when the active session is addressed by realId", () => {
    const onClose = vi.fn();

    render(
      <ExpandablePanel
        visible
        type="history"
        onClose={onClose}
        tasks={[]}
        sessions={[
          {
            id: "temp-1",
            realId: "chat-1",
            name: "current chat by real id",
            messages: [],
          } as any,
        ]}
        onTaskClick={vi.fn()}
        toolbarRef={{ current: document.createElement("div") }}
      />,
    );

    fireEvent.click(screen.getByText("current chat by real id"));

    expect(mocks.setSessionLoading).not.toHaveBeenCalled();
    expect(mocks.navigate).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("loads and navigates when clicking a different session", () => {
    const onClose = vi.fn();

    render(
      <ExpandablePanel
        visible
        type="history"
        onClose={onClose}
        tasks={[]}
        sessions={[
          {
            id: "chat-2",
            name: "other chat",
            messages: [],
          },
        ]}
        onTaskClick={vi.fn()}
        toolbarRef={{ current: document.createElement("div") }}
      />,
    );

    fireEvent.click(screen.getByText("other chat"));

    expect(mocks.setSessionLoading).toHaveBeenCalledWith(true);
    expect(mocks.navigate).toHaveBeenCalledWith("/chat/chat-2", {
      replace: true,
    });
    expect(onClose).toHaveBeenCalled();
  });
});
