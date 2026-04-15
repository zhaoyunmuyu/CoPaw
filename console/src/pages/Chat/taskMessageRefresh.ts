import type { CronJobSpecOutput } from "../../api/types";

interface ShouldRefreshCurrentTaskMessagesOptions {
  previousTask: CronJobSpecOutput | null;
  currentTask: CronJobSpecOutput | null;
}

export function shouldRefreshCurrentTaskMessages({
  previousTask,
  currentTask,
}: ShouldRefreshCurrentTaskMessagesOptions): boolean {
  if (!previousTask || !currentTask) {
    return false;
  }

  if (previousTask.id !== currentTask.id) {
    return false;
  }

  return (
    previousTask.task?.last_scheduled_run_at !==
      currentTask.task?.last_scheduled_run_at ||
    previousTask.task?.unread_execution_count !==
      currentTask.task?.unread_execution_count ||
    previousTask.task?.has_scheduled_result !==
      currentTask.task?.has_scheduled_result
  );
}
