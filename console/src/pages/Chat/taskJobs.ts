import type { CronJobSpecOutput } from "../../api/types";
import { formatListTime } from "./listTimeFormat.ts";

export interface TaskSidebarMeta {
  state: "active" | "auto-paused" | "manual-paused";
  unreadCount: number;
  canResume: boolean;
  canDelete: boolean;
}

const AUTO_PAUSE_REASON = "auto_unread_threshold";

export function isVisibleTask(job: CronJobSpecOutput): boolean {
  return job.task_type === "agent" && Boolean(job.task?.visible_in_my_tasks);
}

export function getTaskSidebarMeta(job: CronJobSpecOutput): TaskSidebarMeta {
  const unreadCount = Math.max(0, Number(job.task?.unread_execution_count || 0));
  const pauseReason = job.task?.pause_reason;
  const isPaused = Boolean(job.task?.is_paused || pauseReason);

  if (pauseReason === AUTO_PAUSE_REASON) {
    return {
      state: "auto-paused",
      unreadCount,
      canResume: true,
      canDelete: true,
    };
  }

  if (isPaused) {
    return {
      state: "manual-paused",
      unreadCount,
      canResume: true,
      canDelete: true,
    };
  }

  return {
    state: "active",
    unreadCount,
    canResume: false,
    canDelete: false,
  };
}

export function shouldMarkTaskReadOnOpen(job: CronJobSpecOutput): boolean {
  return !getTaskSidebarMeta(job).canResume;
}

export function getTaskNextRunText(job: CronJobSpecOutput): string | null {
  if (getTaskSidebarMeta(job).canResume) {
    return null;
  }

  const formatted = formatListTime(job.state?.next_run_at);
  if (!formatted) {
    return null;
  }

  return `下次运行：${formatted}`;
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
