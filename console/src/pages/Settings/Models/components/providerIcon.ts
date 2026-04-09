export const providerIcon = (provider: string) => {
  switch (provider) {
    case "modelscope":
      return "/icons/providers/modelscope.png";
    case "aliyun-codingplan":
      return "/icons/providers/aliyun_codingplan.png";
    case "deepseek":
      return "/icons/providers/deepseek.png";
    case "gemini":
      return "/icons/providers/gemini.png";
    case "azure-openai":
      return "/icons/providers/azure_openai.png";
    case "kimi-cn":
      return "/icons/providers/kimi.png";
    case "kimi-intl":
      return "/icons/providers/kimi.png";
    case "anthropic":
      return "/icons/providers/anthropic.png";
    case "ollama":
      return "/icons/providers/ollama.png";
    case "minimax-cn":
      return "/icons/providers/minimax.png";
    case "minimax":
      return "/icons/providers/minimax.png";
    case "openai":
      return "/icons/providers/openai.png";
    case "dashscope":
      return "/icons/providers/dashscope.png";
    case "lmstudio":
      return "/icons/providers/lmstudio.png";
    case "copaw-local":
      return "/icons/providers/copaw_local.png";
    case "stepfun":
      return "/icons/providers/stepfun.png";
    case "zhipu":
      return "/icons/providers/zhipu.png";
    default:
      return "/icons/providers/default.png";
  }
};
