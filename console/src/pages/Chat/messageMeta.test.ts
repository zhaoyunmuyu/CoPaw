import { describe, expect, it } from "vitest";
import {
  formatMessageTime,
  resolveGroupTimestamp,
  resolveMessageTimestamp,
} from "./messageMeta";

describe("messageMeta", () => {
  it("uses the backend-provided timestamp field", () => {
    const timestamp = resolveMessageTimestamp({
      timestamp: "2026-04-17T08:00:00Z",
    });

    expect(timestamp).toBeTypeOf("number");
    expect(formatMessageTime(timestamp)).toBe("04-17 16:00");
  });

  it("uses the latest backend-provided timestamp in a grouped response", () => {
    const timestamp = resolveGroupTimestamp([
      { timestamp: "2026-04-17T08:00:00Z" },
      { timestamp: "2026-04-17T09:30:00Z" },
    ]);

    expect(timestamp).toBe(
      resolveMessageTimestamp({ timestamp: "2026-04-17T09:30:00Z" }),
    );
    expect(formatMessageTime(timestamp)).toBe("04-17 17:30");
  });
});
