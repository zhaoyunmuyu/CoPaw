import { SparkCopyLine, SparkReplaceLine } from "@agentscope-ai/icons";
import { IAgentScopeRuntimeResponse, AgentScopeRuntimeMessageType } from "../types";
import AgentScopeRuntimeResponseBuilder from "./Builder";
import { Bubble } from "@/chat";
import { Tooltip, message } from "@agentscope-ai/design";
import { copy } from "../../../../Util/copy";
import compact from 'lodash/compact';
import { emit } from "../../Context/useChatAnywhereEventEmitter";
import { useChatAnywhereOptions } from "../../Context/ChatAnywhereOptionsContext";
import { useTranslation } from "../../Context/ChatAnywhereI18nContext";
import React from "react";

/**
 * Extract text content from response output, excluding reasoning messages
 */
function extractTextFromResponse(data: IAgentScopeRuntimeResponse): string {
  if (!data.output || !Array.isArray(data.output)) {
    return JSON.stringify(data);
  }

  const textParts: string[] = [];
  for (const msg of data.output) {
    // Skip reasoning messages
    if (msg.type === AgentScopeRuntimeMessageType.REASONING) {
      continue;
    }
    if (msg.content && Array.isArray(msg.content)) {
      for (const item of msg.content) {
        if (item.type === 'text' && 'text' in item && item.text) {
          textParts.push(item.text);
        }
      }
    }
  }

  return textParts.length > 0 ? textParts.join('\n') : JSON.stringify(data);
}


function Usage(props: {
  input_tokens: string;
  output_tokens: string;
}) {
  if (!props.input_tokens || !props.output_tokens) return null;
  return <Bubble.Footer.Count data={[
    ['Input', props.input_tokens],
    ['Output', props.output_tokens],
  ]} />
}

export default function Tools(props: {
  data: IAgentScopeRuntimeResponse
  isLast?: boolean;
}) {
  const { t } = useTranslation();
  const actionsOptionsList = useChatAnywhereOptions(v => v.actions?.list) || [
    {
      icon: <SparkCopyLine />,
      onClick: () => {
        const text = extractTextFromResponse(props.data);
        copy(text).then(() => {
          message.success('复制成功');
        }).catch(() => {
          message.error('复制失败');
        });
      }
    }
  ];

  const replace = useChatAnywhereOptions(v => v.actions?.replace) ?? true;

  const actions = compact([
    ...actionsOptionsList.map(i => {
      const res = i;

      if (i.render) {
        res.children = React.createElement(i.render, { data: props });
      }
      return {
        ...res, onClick() {
          i.onClick?.(props);
        }
      }
    }),
    replace && props.isLast ? {
      icon: <Tooltip title={t?.('actions.regenerate') || '重新生成'}><SparkReplaceLine /></Tooltip>,
      onClick: () => {
        emit({
          type: 'handleReplace',
          data: props,
        })
      }
    } : null,
  ]);


  if (!AgentScopeRuntimeResponseBuilder.maybeDone(props.data)) return null;
  return <Bubble.Footer
    left={<Bubble.Footer.Actions data={actions} />}
    right={<Usage input_tokens={props.data.usage?.input_tokens} output_tokens={props.data.usage?.output_tokens} />}
  />
}

