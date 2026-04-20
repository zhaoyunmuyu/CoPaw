import { useChatAnywhereMessages } from "../Context/ChatAnywhereMessagesContext";
import { IAgentScopeRuntimeWebUIInputData } from "./IChatAnywhere";

export interface IAgentScopeRuntimeWebUIRef {
  messages: ReturnType<typeof useChatAnywhereMessages>;
  input: {
    setDisabled: (disabled: boolean) => void;
    submit: (data: IAgentScopeRuntimeWebUIInputData) => void;
    setContent: (content: string) => void;
  };
  createSession: (data?: { name?: string }) => Promise<string | undefined>;
  refreshSession: (sessionId?: string) => Promise<boolean>;
}
