/**
 * Greeting API module
 */
import { request } from "../request";
import type {
  GreetingConfig,
  GreetingConfigCreate,
  GreetingConfigUpdate,
  GreetingDisplay,
  GreetingConfigListResponse,
} from "../types/greeting";

export const greetingApi = {
  /** Get greeting for current context (from X-Source-Id and X-Bbk-Id headers) */
  getDisplayGreeting: () =>
    request<GreetingDisplay | null>("/greeting/display"),

  /** Admin: list all greeting configs */
  listConfigs: (params?: {
    source_id?: string;
    page?: number;
    page_size?: number;
  }) =>
    request<GreetingConfigListResponse>("/greeting/admin/list", { params }),

  /** Admin: create greeting config */
  createConfig: (config: GreetingConfigCreate) =>
    request<{ success: boolean; data: GreetingConfig }>("/greeting/admin", {
      method: "POST",
      body: JSON.stringify(config),
    }),

  /** Admin: update greeting config */
  updateConfig: (id: number, config: GreetingConfigUpdate) =>
    request<{ success: boolean; data: GreetingConfig }>(
      `/greeting/admin/${id}`,
      {
        method: "PUT",
        body: JSON.stringify(config),
      }
    ),

  /** Admin: delete greeting config */
  deleteConfig: (id: number) =>
    request<{ success: boolean }>(`/greeting/admin/${id}`, {
      method: "DELETE",
    }),
};
