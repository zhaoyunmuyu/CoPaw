import type { TFunction } from "i18next";

const defaultConfig = {
  theme: {
    colorPrimary: "#3769FC",
    darkMode: false,
    prefix: "swe",
    leftHeader: {
      logo: "",
      title: "",
      // title: "Work with Swe",
    },
  },
  sender: {
    attachments: true,
    maxLength: 10000,
    disclaimer: "Works for you, grows with you",
  },
  welcome: {
    greeting: "Hello, how can I help you today?",
    description:
      "I am a helpful assistant that can help you with your questions.",
    avatar: `${import.meta.env.BASE_URL}swe-symbol.png`,
    prompts: [
      {
        value: "Let's start a new journey!",
      },
      {
        value: "Can you tell me what skills you have?",
      },
    ],
  },
  api: {
    baseURL: "",
    token: "",
  },
} as const;

export function getDefaultConfig(t: TFunction) {
  return {
    ...defaultConfig,
    sender: {
      ...defaultConfig.sender,
      disclaimer: "",
      // disclaimer: t("chat.disclaimer"),
    },
    welcome: {
      ...defaultConfig.welcome,
      // greeting: t("chat.greeting"),
      // description: t("chat.description"),
      greeting: t("chat.description"),
      description: "",
      prompts: [
        { value: t("chat.prompt1") },
        { value: "3月12日至3月19日上证指数累计下跌达3.07%，帮我找到可能受影响的客户，并提供沟通建议" },
        { value: "帮我监控管户客户风险异动" },
        { value: "我需要营销基金007119，帮我找客户" },
      ],
    },
  };
}

export default defaultConfig;

export type DefaultConfig = typeof defaultConfig;
