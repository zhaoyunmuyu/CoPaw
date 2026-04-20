import { describe, expect, it } from "vitest";
import { getAgentDisplayName } from "./agentDisplayName";

describe("getAgentDisplayName", () => {
  it("uses 小助 Claw for the default agent", () => {
    const label = getAgentDisplayName(
      { id: "default", name: "" },
      ((key: string) =>
        key === "agent.defaultDisplayName" ? "小助 Claw" : key) as never,
    );

    expect(label).toBe("小助 Claw");
  });
});
