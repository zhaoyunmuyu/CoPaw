import { describe, expect, it, vi } from "vitest";
import {
  resolveResponseHeaderTimestamp,
  withRequestHeaderMeta,
  withResponseHeaderMeta,
} from "./headerMeta";

describe("headerMeta helpers", () => {
  it("attaches a stable local timestamp to live request cards", () => {
    const timestamp = Date.parse("2026-04-17T16:00:00+08:00");

    expect(withRequestHeaderMeta({ input: [] }, timestamp)).toEqual({
      input: [],
      headerMeta: {
        timestamp,
      },
    });
  });

  it("prefers the existing live response timestamp during stream updates", () => {
    const currentTimestamp = Date.parse("2026-04-17T16:01:00+08:00");
    const createdAt = Date.parse("2026-04-17T16:02:00+08:00");

    expect(
      resolveResponseHeaderTimestamp({ created_at: createdAt }, currentTimestamp),
    ).toBe(
      currentTimestamp,
    );
    expect(
      withResponseHeaderMeta(
        { id: "r1", created_at: createdAt, output: [] },
        currentTimestamp,
      ).headerMeta.timestamp,
    ).toBe(currentTimestamp);
  });

  it("falls back to now when no live timestamp exists", () => {
    const createdAt = Date.parse("2026-04-17T16:03:00+08:00");
    const now = createdAt + 1000;
    const dateNow = vi.spyOn(Date, "now").mockReturnValue(now);

    expect(resolveResponseHeaderTimestamp({ created_at: createdAt })).toBe(now);
    expect(resolveResponseHeaderTimestamp(undefined)).toBe(now);

    dateNow.mockRestore();
  });

  it("prefers the latest output message timestamp for live agent headers", () => {
    const responseTimestamp = Date.parse("2026-04-17T16:04:00+08:00");
    const outputTimestamp = "2026-04-17T08:06:00Z";

    expect(
      resolveResponseHeaderTimestamp({
        created_at: responseTimestamp,
        output: [{ timestamp: "2026-04-17T08:05:00Z" }, { timestamp: outputTimestamp }],
      }),
    ).toBe(Date.parse(outputTimestamp));

    expect(
      withResponseHeaderMeta({
        id: "r2",
        created_at: responseTimestamp,
        output: [{ timestamp: outputTimestamp }],
      }).headerMeta.timestamp,
    ).toBe(Date.parse(outputTimestamp));
  });
});
