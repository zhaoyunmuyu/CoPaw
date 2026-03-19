import { request } from "../request";

export interface PushMessage {
  id: string;
  text: string;
}

export const consoleApi = {
  getPushMessages: () =>
    request<{ messages: PushMessage[] }>("/console/push-messages", {
      headers: {
        "x-user-id": (window as any).currentUserId || "default",
      },
    }),
};
