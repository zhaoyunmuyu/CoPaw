import { request } from "../request";
import { cronAccessKey, cronContextHeaders } from "../cronTaskContext";
import type { CronJobSpecOutput } from "../types/cronjob";
import type {
  ManagedCronContext,
  ManagedJob,
  ManagedJobDetail,
} from "../types/schedulerCron";
import type {
  CronTaskOrigin,
  SourcedCronTask,
  SourcedManagedTask,
  TaskPresence,
  TaskSourceSnapshot,
} from "../types/cronTaskSource";
import { schedulerCronApi } from "./schedulerCron";

export function taskOrigin(task: CronJobSpecOutput): CronTaskOrigin | null {
  return (task as Partial<SourcedCronTask>).clientTaskOrigin ?? null;
}

export function isSchedulerTask(
  task: CronJobSpecOutput,
): task is SourcedManagedTask {
  return taskOrigin(task)?.owner === "scheduler";
}

export function tagTask(
  task: CronJobSpecOutput,
  owner: CronTaskOrigin["owner"],
  context: ManagedCronContext,
  accessKey = cronAccessKey(context),
): SourcedCronTask {
  return {
    ...task,
    clientTaskOrigin: { owner, context: { ...context }, accessKey },
  };
}

export function taskIdentityKey(task: CronJobSpecOutput): string {
  const origin = taskOrigin(task);
  if (!origin) return task.id;
  return JSON.stringify([
    origin.owner,
    origin.context.tenant_id,
    origin.context.source_id,
    origin.context.agent_id,
    task.id,
  ]);
}

export function sameTask(
  left: CronJobSpecOutput,
  right: CronJobSpecOutput,
): boolean {
  return taskIdentityKey(left) === taskIdentityKey(right);
}

function managedTask(
  job: ManagedJob,
  context: ManagedCronContext,
  accessKey: string,
): SourcedManagedTask {
  if (
    job.management_owner !== "scheduler" ||
    !Number.isInteger(job.definition_version) ||
    job.definition_version < 1 ||
    job.tenant_id !== context.tenant_id ||
    job.source_id !== context.source_id ||
    job.agent_id !== context.agent_id
  )
    throw new Error("invalid_managed_task_identity");
  return tagTask(job, "scheduler", context, accessKey) as SourcedManagedTask;
}

/** 仅查询新任务；失败保留已知的新任务，不回退旧文件任务。 */
export async function listTaskSources(
  context: ManagedCronContext,
  signal?: AbortSignal,
): Promise<TaskSourceSnapshot> {
  const accessKey = cronAccessKey(context);
  const [newResult] = await Promise.allSettled([
    schedulerCronApi
      .listAll(context, { signal })
      .then((jobs) => jobs.map((job) => managedTask(job, context, accessKey))),
  ]);
  const errors: string[] = [];
  if (newResult.status === "rejected")
    errors.push("新版任务列表暂不可用，保留已知任务");
  return {
    legacy: [],
    scheduler: newResult.status === "fulfilled" ? newResult.value : null,
    errors,
  };
}

export function mergeTaskSources(
  previous: CronJobSpecOutput[],
  snapshot: TaskSourceSnapshot,
): CronJobSpecOutput[] {
  const newJobs = snapshot.scheduler ?? previous.filter(isSchedulerTask);
  return newJobs;
}

export function taskPresence(snapshot: TaskSourceSnapshot): TaskPresence {
  const ids = (jobs: CronJobSpecOutput[] | null) =>
    jobs === null ? null : new Set(jobs.map((job) => job.id));
  return { legacy: ids(snapshot.legacy), scheduler: ids(snapshot.scheduler) };
}

async function optionalDetail<T>(
  context: ManagedCronContext,
  path: string,
): Promise<T | null> {
  try {
    return await request<T>(path, { headers: cronContextHeaders(context) });
  } catch (error) {
    if (
      error &&
      typeof error === "object" &&
      "status" in error &&
      error.status === 404
    )
      return null;
    throw error;
  }
}

/** 裸 ID 仅从 Scheduler 确认归属，不探测旧接口或用写入试探。 */
export async function resolveTaskOrigin(
  context: ManagedCronContext,
  id: string,
): Promise<CronTaskOrigin> {
  const accessKey = cronAccessKey(context);
  const encoded = encodeURIComponent(id);
  const [newResult] = await Promise.allSettled([
    optionalDetail<ManagedJobDetail>(
      context,
      `/scheduler/cron/jobs/${encoded}`,
    ),
  ]);
  if (newResult.status === "rejected")
    throw new Error("无法确认报告任务归属，未标记已读");
  const newJob = newResult.value;
  if (newJob) {
    if (
      newJob.management_owner !== "scheduler" ||
      newJob.spec.id !== id ||
      newJob.spec.tenant_id !== context.tenant_id ||
      newJob.spec.source_id !== context.source_id ||
      newJob.agent_id !== context.agent_id
    )
      throw new Error("无法确认报告任务完整身份，未标记已读");
    return { owner: "scheduler", context: { ...context }, accessKey };
  }
  throw new Error("报告任务不存在，未标记已读");
}
