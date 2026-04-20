import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { formatMessageTime } from "../messageMeta";
import RuntimeRequestCard from "./RuntimeRequestCard";
import RuntimeResponseCard from "./RuntimeResponseCard";

vi.mock(
  "@/components/agentscope-chat/AgentScopeRuntimeWebUI/core/AgentScopeRuntime/Request/Card",
  () => ({
    default: () => <div data-testid="request-card-body">request-body</div>,
  }),
);

vi.mock(
  "@/components/agentscope-chat/AgentScopeRuntimeWebUI/core/AgentScopeRuntime/Response/Card",
  () => ({
    default: () => <div data-testid="response-card-body">response-body</div>,
  }),
);

describe("runtime message header cards", () => {
  it("renders user header meta above the request card on the right side", () => {
    const timestamp = Date.parse("2026-04-17T08:00:00Z");
    const { container } = render(
      <RuntimeRequestCard
        data={{
          input: [],
          headerMeta: { timestamp },
        } as never}
      />,
    );

    expect(screen.getByText("我")).toBeInTheDocument();
    expect(screen.getByText(formatMessageTime(timestamp))).toBeInTheDocument();
    expect(screen.getByTestId("request-card-body")).toBeInTheDocument();
    expect(container.firstElementChild?.className).toContain("messageBlockEnd");
  });

  it("renders agent header meta above the response card on the left side", () => {
    const timestamp = Date.parse("2026-04-17T09:30:00Z");
    const { container } = render(
      <RuntimeResponseCard
        data={{
          output: [],
          headerMeta: { timestamp },
        } as never}
      />,
    );

    expect(screen.getByText("小助 Claw")).toBeInTheDocument();
    expect(screen.getByText(formatMessageTime(timestamp))).toBeInTheDocument();
    expect(screen.getByTestId("response-card-body")).toBeInTheDocument();
    expect(container.firstElementChild?.className).toContain("messageBlockStart");
  });
});
