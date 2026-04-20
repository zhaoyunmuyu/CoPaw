import React, { useState } from "react";
import { Tooltip } from "antd";
import { useProviderContext } from "@/components/agentscope-chat";
import { SparkRightArrowLine } from "@agentscope-ai/icons";
import { AgentScopeRuntimeRunStatus } from "../types";
import { emit } from "../../Context/useChatAnywhereEventEmitter";
import Style from "./style";

export interface ISuggestionsProps {
  /**
   * @description 建议问题列表
   */
  suggestions: string[];
  /**
   * @description 当前响应状态
   */
  status: AgentScopeRuntimeRunStatus;
}

export default function Suggestions(props: ISuggestionsProps) {
  const { suggestions, status } = props;
  const prefixCls = useProviderContext().getPrefixCls("suggestions");
  const [tooltipVisible, setTooltipVisible] = useState<string | null>(null);

  // 没有建议内容时不渲染
  if (!suggestions?.length) {
    return null;
  }

  // 是否正在生成响应
  const isGenerating = status === AgentScopeRuntimeRunStatus.InProgress;

  const handleClick = (query: string) => {
    if (isGenerating) {
      // 正在生成时显示提示，不发起提问
      setTooltipVisible(query);
      setTimeout(() => setTooltipVisible(null), 1500);
      return;
    }
    // 空闲时通过事件触发提交
    emit({
      type: "handleSubmit",
      data: { query },
    });
  };

  return (
    <>
      <Style />
      <div className={prefixCls}>
        <div className={`${prefixCls}-header`}>
          <div className={`${prefixCls}-label`}>猜你想问</div>
        </div>
        <div className={`${prefixCls}-list`}>
          {suggestions.map((suggestion, index) => (
            <Tooltip
              key={suggestion}
              title={tooltipVisible === suggestion ? "正在回复中，请稍候..." : ""}
              open={tooltipVisible === suggestion || undefined}
              mouseEnterDelay={0.3}
            >
              <div
                className={`${prefixCls}-item`}
                onClick={() => handleClick(suggestion)}
              >
                <span className={`${prefixCls}-item-text`}>
                  {suggestion}
                </span>
                <SparkRightArrowLine className={`${prefixCls}-item-icon`} />
              </div>
            </Tooltip>
          ))}
        </div>
      </div>
    </>
  );
}