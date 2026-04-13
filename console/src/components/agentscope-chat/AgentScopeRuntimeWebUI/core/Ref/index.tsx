import React, { forwardRef } from "react";
import { useContextSelector } from "use-context-selector";
import {
  ChatAnywhereMessagesContext,
  useChatAnywhereMessages,
} from "../Context/ChatAnywhereMessagesContext";
import {
  ChatAnywhereInputContext,
  useChatAnywhereInput,
} from "../Context/ChatAnywhereInputContext";
import { emit } from "../Context/useChatAnywhereEventEmitter";
import { IAgentScopeRuntimeWebUIInputData } from "../types";
import { useChatAnywhereSessions } from "../Context/ChatAnywhereSessionsContext";

// 逐步放开
function Ref(_, ref) {
  const messages = useChatAnywhereMessages();
  const setDisabled = useContextSelector(
    ChatAnywhereInputContext,
    (v) => v.setDisabled,
  );
  const { createSession } = useChatAnywhereSessions();

  React.useImperativeHandle(
    ref,
    () => {
      return {
        messages,
        input: {
          setDisabled,
          submit: (data: IAgentScopeRuntimeWebUIInputData) => {
            const { query, fileList, biz_params } = data;
            emit({
              type: "handleSubmit",
              data: { query, fileList, biz_params },
            });
          },
        },
        createSession,
      };
    },
    [messages, createSession],
  );

  return null;
}

export default forwardRef(Ref);
