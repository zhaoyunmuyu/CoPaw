import type { CronJobSpecOutput } from "@/api/types";
import type { ManagedCronSchedule } from "@/api/types/schedulerCron";
import dayjs from "dayjs";
import {
  buildCronJobFormValues,
  buildCronJobSubmitPayload,
  type CronJobFormValues,
} from "../CronJobs/helpers";
import {
  CronType,
  parseCron,
  serializeCron,
} from "../CronJobs/components/parseCron";

export type ManagedFormValues = CronJobFormValues & {
  schedule: ManagedCronSchedule;
};
const LAST_WORKDAY = "lastWorkday";

function lastWorkdayParts(cron: string) {
  const match = cron.trim().match(/^(\d{1,2})\s+(\d{1,2})\s+LW\s+\*\s+\*$/i);
  if (!match || Number(match[1]) > 59 || Number(match[2]) > 23) return null;
  return { minute: Number(match[1]), hour: Number(match[2]) };
}

/** 只适配新版编辑器，不改变旧页面的表单转换行为。 */
export function buildManagedCronFormValues(
  job: CronJobSpecOutput,
): ManagedFormValues {
  const values: ManagedFormValues = buildCronJobFormValues(job);
  const schedule = job.schedule as ManagedCronSchedule;
  values.schedule = {
    ...schedule,
    run_on_non_workday: schedule.run_on_non_workday ?? false,
  };
  const cron = job.schedule.cron;
  const parts = parseCron(cron);
  const workday = lastWorkdayParts(cron);
  if (workday && schedule.timezone === "Asia/Shanghai") {
    values.cronType = LAST_WORKDAY;
    values.cronTime = dayjs().hour(workday.hour).minute(workday.minute);
  } else if (
    parts.type === CronType.daily &&
    (parts.hours?.length ?? 1) === 1
  ) {
    values.cronTime = values.cronTime?.hour(
      parts.hours?.[0] ?? parts.hour ?? 9,
    );
  } else if (parts.type !== CronType.hourly && parts.type !== CronType.weekly) {
    // 原表单没有多小时、月/年或分钟间隔控件，使用已有自定义输入。
    values.cronType = CronType.custom;
    values.cronCustom = cron;
  }
  return values;
}

export function buildManagedCronSubmitPayload(
  values: ManagedFormValues,
  original?: CronJobSpecOutput | null,
) {
  const lastWorkday = values.cronType === LAST_WORKDAY;
  const time = values.cronTime ?? dayjs().hour(9).minute(0);
  const source = lastWorkday
    ? {
        ...values,
        cronType: CronType.custom,
        cronCustom: `${time.minute()} ${time.hour()} LW * *`,
        schedule: { ...values.schedule, timezone: "Asia/Shanghai" },
      }
    : values;
  const payload = buildCronJobSubmitPayload(source);
  const previous = original ? lastWorkdayParts(original.schedule.cron) : null;
  if (
    original &&
    ((lastWorkday &&
      previous?.hour === time.hour() &&
      previous.minute === time.minute()) ||
      serializeCron(parseCron(payload.schedule.cron)) ===
        serializeCron(parseCron(original.schedule.cron)))
  ) {
    // 只改名称等其他字段时，保留原Cron文本（包括数字星期等写法）。
    payload.schedule.cron = original.schedule.cron;
  }
  return {
    ...payload,
    schedule: {
      ...payload.schedule,
      run_on_non_workday: values.schedule.run_on_non_workday ?? false,
    },
  };
}
