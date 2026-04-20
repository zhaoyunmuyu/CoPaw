import { IAgentScopeRuntimeWebUIInputData } from "../../types";

export const FOLLOW_UP_STOP_BACKOFF_MS = [300, 600, 1000] as const;
export const FOLLOW_UP_SUBMIT_FAILED_EVENT =
  "agentscope-runtime:follow-up-submit-failed";
export const RUNTIME_INPUT_SET_CONTENT_EVENT =
  "agentscope-runtime:set-input-content";

export type FollowUpSubmitData = Pick<
  IAgentScopeRuntimeWebUIInputData,
  "query" | "fileList" | "biz_params"
>;

export type RuntimeInputRestorePayload = {
  content: string;
  fileList?: FollowUpSubmitData["fileList"];
  biz_params?: FollowUpSubmitData["biz_params"];
};

function defaultSleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

type FollowUpSubmitCoordinatorOptions = {
  stop: () => Promise<void>;
  submit: (data: FollowUpSubmitData) => Promise<void>;
  isGenerating: () => Promise<boolean>;
  restoreInput: (data: FollowUpSubmitData) => void;
  notifyFailure: () => void;
  sleepMs?: (ms: number) => Promise<void>;
};

export async function stopUntilGenerationEnds({
  stop,
  isGenerating,
  sleepMs = defaultSleep,
  retryBackoffMs = FOLLOW_UP_STOP_BACKOFF_MS,
}: {
  stop: () => Promise<void>;
  isGenerating: () => Promise<boolean>;
  sleepMs?: (ms: number) => Promise<void>;
  retryBackoffMs?: readonly number[];
}): Promise<boolean> {
  const tryStop = async () => {
    try {
      await stop();
    } catch {
      // Stop is best-effort here; generating state decides completion.
    }
  };

  await tryStop();
  if (!(await isGenerating())) {
    return true;
  }

  for (const delayMs of retryBackoffMs) {
    await sleepMs(delayMs);
    if (!(await isGenerating())) {
      return true;
    }

    await tryStop();
    if (!(await isGenerating())) {
      return true;
    }
  }

  return !(await isGenerating());
}

export class FollowUpSubmitCoordinator {
  private pending: FollowUpSubmitData | null = null;
  private activeRun: Promise<void> | null = null;

  constructor(
    private readonly options: FollowUpSubmitCoordinatorOptions,
    private readonly retryBackoffMs: readonly number[] = FOLLOW_UP_STOP_BACKOFF_MS,
  ) {}

  enqueue(data: FollowUpSubmitData): Promise<void> {
    this.pending = data;

    if (!this.activeRun) {
      this.activeRun = this.run();
    }

    return this.activeRun;
  }

  private async run(): Promise<void> {
    try {
      while (this.pending) {
        const stopped = await stopUntilGenerationEnds({
          stop: this.options.stop,
          isGenerating: this.options.isGenerating,
          sleepMs: this.options.sleepMs,
          retryBackoffMs: this.retryBackoffMs,
        });

        const latestPending = this.pending;
        this.pending = null;

        if (!latestPending) {
          return;
        }

        if (!stopped) {
          this.options.restoreInput(latestPending);
          this.options.notifyFailure();
          return;
        }

        await this.options.submit(latestPending);
      }
    } finally {
      this.activeRun = null;
    }
  }
}
