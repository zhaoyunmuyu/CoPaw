import React, { useMemo } from "react";
import { OperateCard } from "@/components/agentscope-chat";
import {
  SparkLoadingLine,
  SparkToolLine,
  SparkFalseLine,
} from "@agentscope-ai/icons";
import DownloadFileCard from "../../DownloadFileCard";
import { IAgentScopeRuntimeMessage, AgentScopeRuntimeRunStatus } from "../core/AgentScopeRuntime/types";

interface CopyFileToStaticData {
  name: string;
  arguments: { file_path: string };
  output: { ok: boolean; path?: string; message?: string; error?: string };
}

interface CopyFileToStaticProps {
  data: IAgentScopeRuntimeMessage;
}

/**
 * Extract plain text from various output formats
 * Handles: string, JSON string, array with type="text" items
 */
function extractPlainText(value: any): string | null {
  if (!value) return null;
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (!trimmed) return value;
    if (
      (trimmed.startsWith("[") && trimmed.endsWith("]")) ||
      (trimmed.startsWith("{") && trimmed.endsWith("}"))
    ) {
      try {
        return extractPlainText(JSON.parse(trimmed));
      } catch {
        return value;
      }
    }
    return value;
  }
  if (Array.isArray(value)) {
    const texts = value
      .map((item) => extractPlainText(item))
      .filter((item): item is string => !!item);
    return texts.length ? texts.join("\n") : null;
  }
  if (value.type === "text" && typeof value.text === "string") {
    return value.text;
  }
  if (typeof value.text === "string") {
    return value.text;
  }
  return null;
}

/**
 * Parse the tool output JSON to extract filename and URL
 * Output format: { ok: true, path: "![filename](url)", message: "..." }
 */
function parseToolOutput(output: CopyFileToStaticData["output"]): {
  success: boolean;
  fileName?: string;
  url?: string;
  error?: string;
} {
  if (!output) {
    return { success: false, error: "无输出" };
  }

  // Extract plain text from nested formats
  const plainText = extractPlainText(output);
  let parsedOutput: any;

  if (plainText) {
    // Try to parse as JSON
    try {
      parsedOutput = JSON.parse(plainText);
    } catch {
      return { success: false, error: "输出格式无效" };
    }
  } else {
    parsedOutput = output;
  }

  if (!parsedOutput.ok) {
    return { success: false, error: parsedOutput.error || "工具执行失败" };
  }

  if (!parsedOutput.path) {
    return { success: false, error: "未返回文件路径" };
  }

  // Parse markdown image link: ![filename](url)
  const pathMatch = parsedOutput.path.match(/!\[([^\]]+)\]\(([^)]+)\)/);
  if (!pathMatch) {
    return { success: false, error: "路径格式无效" };
  }

  const fileName = pathMatch[1];
  const url = pathMatch[2];

  return { success: true, fileName, url };
}

function CopyFileToStatic(props: CopyFileToStaticProps) {
  const { data } = props;
  const prefixCls = "swe-operate-card";

  // Check if tool is still running
  const loading = data.status === AgentScopeRuntimeRunStatus.InProgress;

  // Extract input and output from tool message
  const content = data.content as Array<{ data?: CopyFileToStaticData }>;
  const input = content[0]?.data?.arguments?.file_path || "";
  const output = content[1]?.data?.output;

  // Parse output
  const parsedOutput = useMemo(() => parseToolOutput(output), [output]);

  // Render content
  const renderContent = useMemo(() => {
    if (loading) {
      return (
        <div className={`${prefixCls}-tool-call-loading`}>
          <SparkLoadingLine spin />
          <span>正在处理文件...</span>
        </div>
      );
    }

    if (!parsedOutput.success) {
      return (
        <div className={`${prefixCls}-tool-call-error`}>
          <SparkFalseLine style={{ color: "#ff4d4f" }} />
          <span>{parsedOutput.error}</span>
        </div>
      );
    }

    return (
      <DownloadFileCard
        url={parsedOutput.url!}
        fileName={parsedOutput.fileName}
      />
    );
  }, [loading, parsedOutput, prefixCls]);

  return (
    <OperateCard
      header={{
        icon: loading ? <SparkLoadingLine spin /> : <SparkToolLine />,
        title: loading ? "复制文件到静态目录" : "文件已就绪",
        description: input ? `源文件: ${input}` : undefined,
      }}
      body={{
        defaultOpen: true,
        children: (
          <div className={`${prefixCls}-tool-call-body`}>
            {renderContent}
          </div>
        ),
      }}
    />
  );
}

export default CopyFileToStatic;