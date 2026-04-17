export interface CronJobSchedule {
  type: "cron";
  cron: string;
  timezone?: string;
}

export interface CronJobTarget {
  user_id: string;
  session_id: string;
}

export interface CronJobDispatch {
  type: "channel";
  channel?: string;
  target: CronJobTarget;
  mode?: "stream" | "final";
  meta?: Record<string, unknown>;
}

export interface CronJobRuntime {
  max_concurrency?: number;
  timeout_seconds?: number;
  misfire_grace_seconds?: number;
}

export interface CronJobRequest {
  input: unknown;
  session_id?: string | null;
  user_id?: string | null;
  [key: string]: unknown;
}

export interface CronJobState {
  next_run_at?: string | null;
  last_run_at?: string | null;
  last_status?: "success" | "error" | "running" | "skipped" | "cancelled" | null;
  last_error?: string | null;
}

export interface CronTaskView {
  visible_in_my_tasks: boolean;
  chat_id?: string | null;
  session_id?: string | null;
  has_scheduled_result: boolean;
  latest_scheduled_preview: string;
  unread_execution_count: number;
  last_scheduled_run_at?: string | null;
  is_running: boolean;
  is_paused?: boolean;
  pause_reason?: "manual" | "auto_unread_threshold" | null;
  auto_paused_at?: string | null;
}

export interface CronJobSpecInput {
  id: string;
  name: string;
  enabled?: boolean;
  schedule: CronJobSchedule;
  task_type?: "text" | "agent";
  text?: string;
  request?: CronJobRequest;
  dispatch: CronJobDispatch;
  runtime?: CronJobRuntime;
  meta?: Record<string, unknown>;
}

export interface CronJobSpecOutput extends CronJobSpecInput {
  state?: CronJobState;
  task?: CronTaskView | null;
}

export interface CronJobView {
  spec: CronJobSpecOutput;
  state?: CronJobState;
  task?: CronTaskView | null;
}

export type CronJobSpecInputLegacy = Record<string, unknown>;
export type CronJobSpecOutputLegacy = Record<string, unknown>;
export type CronJobViewLegacy = Record<string, unknown>;
