import React from "react";
import {
  AgentScopeRuntimeRunStatus,
  IAgentScopeRuntimeMessage,
  IDataContent,
} from "../types";
import { ToolCall } from "@/components/agentscope-chat";
import { useChatAnywhereOptions } from "../../Context/ChatAnywhereOptionsContext";
import Approval from "./Approval";

const TOOL_DISPLAY_NAMES: Record<string, string> = {
  read_file: "读取文件",
  write_file: "写入文件",
  edit_file: "编辑文件",
  append_file: "追加文件",
  execute_shell_command: "执行操作",
  grep_search: "内容搜索",
  glob_search: "文件查找",
  memory_search: "记忆检索",
  browser_use: "网页操作",
  desktop_screenshot: "截取屏幕",
  get_current_time: "获取时间",
  set_user_timezone: "设置时区",
  view_image: "查看图片",
  view_video: "查看视频",
  send_file_to_user: "发送文件",
};

function getToolDisplayName(toolName?: string, serverLabel?: string) {
  const label = toolName
    ? TOOL_DISPLAY_NAMES[toolName] || "工具操作"
    : "工具操作";
  return serverLabel ? `[${serverLabel}] ${label}` : label;
}

const Tool = React.memo(function ({
  data,
  isApproval = false,
}: {
  data: IAgentScopeRuntimeMessage;
  isApproval?: boolean;
}) {
  const customToolRenderConfig =
    useChatAnywhereOptions((v) => v.customToolRenderConfig) || {};

  if (!data.content?.length) return null;
  const content = data.content as IDataContent<{
    name: string;
    server_label?: string;
    arguments: Record<string, any>;
    output: Record<string, any>;
    summary?: string;
    output_summary?: string;
  }>[];
  const loading = data.status === AgentScopeRuntimeRunStatus.InProgress;
  const toolName = content[0].data.name;
  const serverLabel = content[0].data.server_label;
  const defaultTitle = getToolDisplayName(toolName, serverLabel);

  const title = content[0].data.summary || defaultTitle;
  const input = content[0]?.data?.arguments;
  const output = content[1]?.data?.output;
  const outputSummary = content[1]?.data?.output_summary;

  let node;

  if (customToolRenderConfig[toolName]) {
    const C = customToolRenderConfig[toolName];
    node = <C data={data} />;
  } else {
    node = (
      <ToolCall
        loading={loading}
        defaultOpen={false}
        title={title === "undefined" ? defaultTitle : title}
        subTitle={defaultTitle}
        input={input}
        output={output}
        outputSummary={outputSummary}
      ></ToolCall>
    );
  }

  return (
    <>
      {node}
      {isApproval && <Approval data={data} />}
    </>
  );
});

export default Tool;
