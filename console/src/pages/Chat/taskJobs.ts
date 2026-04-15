import type { CronJobSpecOutput } from "../../api/types";

export function isVisibleTask(job: CronJobSpecOutput): boolean {
  return job.task_type === "agent" && Boolean(job.task?.visible_in_my_tasks);
}

export function deriveChatTaskState(
  jobs: CronJobSpecOutput[],
  chatId: string | undefined,
): {
  tasks: CronJobSpecOutput[];
  currentTask: CronJobSpecOutput | null;
} {
  return {
    tasks: jobs.filter(isVisibleTask),
    currentTask: chatId
      ? jobs.find((job) => job.task?.chat_id === chatId) || null
      : null,
  };
}
