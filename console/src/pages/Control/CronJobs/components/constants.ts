import dayjs from "dayjs";

// ==================== userId 统一整改 (Kun He) ====================
// 使用统一的 DEFAULT_USER_ID 常量
import { DEFAULT_USER_ID } from "../../../../utils/identity";
// ==================== userId 统一整改结束 ====================

export { TIMEZONE_OPTIONS } from "../../../../constants/timezone";

export const DEFAULT_FORM_VALUES = {
  enabled: false,
  schedule: {
    type: "cron" as const,
    cron: "0 9 * * *",
    timezone: "UTC",
  },
  cronType: "daily",
  cronTime: dayjs().hour(9).minute(0),
  task_type: "agent" as const,
  dispatch: {
    type: "channel" as const,
    channel: "console",
    target: {
      // ==================== userId 统一整改 (Kun He) ====================
      // 使用 DEFAULT_USER_ID 替代空字符串
      user_id: DEFAULT_USER_ID,
      // ==================== userId 统一整改结束 ====================
      session_id: "",
    },
    mode: "final" as const,
  },
  runtime: {
    max_concurrency: 1,
    timeout_seconds: 7200,
    misfire_grace_seconds: 300,
  },
};
