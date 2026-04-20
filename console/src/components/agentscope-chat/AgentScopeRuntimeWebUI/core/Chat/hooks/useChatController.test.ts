import { describe, expect, it } from "vitest";
import { shouldEnqueueFollowUpSubmission } from "./followUpSubmitState";

describe("shouldEnqueueFollowUpSubmission", () => {
  it("treats loading as generating so auto-submit cannot be bypassed mid-run", () => {
    expect(shouldEnqueueFollowUpSubmission(true, false)).toBe(true);
  });

  it("treats session generating as generating even when loading is false", () => {
    expect(shouldEnqueueFollowUpSubmission(false, true)).toBe(true);
  });

  it("allows direct submit only when neither loading nor generating", () => {
    expect(shouldEnqueueFollowUpSubmission(false, false)).toBe(false);
  });
});
