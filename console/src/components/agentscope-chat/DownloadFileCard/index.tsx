import React, { useMemo, useState } from "react";
import { SparkDownloadLine } from "@agentscope-ai/icons";
import FilePreviewModal from "../FilePreviewModal";
import { getFileIcon, getFileType } from "../FilePreviewModal/fileUtils";

export interface DownloadFileCardProps {
  url: string;
  fileName?: string;
  className?: string;
  style?: React.CSSProperties;
}

const EMPTY = "\u00A0";

// 内联样式定义
const cardStyle: React.CSSProperties = {
  position: "relative",
  display: "flex",
  alignItems: "center",
  padding: "12px 16px",
  background: "#fff",
  border: "1px solid #d9d9d9",
  borderRadius: "8px",
  cursor: "pointer",
  transition: "all 0.3s",
  maxWidth: "280px",
  overflow: "hidden",
};

const iconStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  width: "24px",
  height: "24px",
  marginRight: "8px",
  flexShrink: 0,
};

const contentStyle: React.CSSProperties = {
  flex: 1,
  minWidth: 0,
  display: "flex",
  flexDirection: "column",
  gap: "4px",
};

const nameStyle: React.CSSProperties = {
  fontSize: "14px",
  fontWeight: 500,
  color: "#262626",
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};

const hintStyle: React.CSSProperties = {
  fontSize: "12px",
  color: "#8c8c8c",
};

const downloadBtnStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  width: "24px",
  height: "24px",
  background: "#1677ff",
  borderRadius: "4px",
  color: "#fff",
  cursor: "pointer",
  flexShrink: 0,
  marginLeft: "8px",
};

function DownloadFileCard(props: DownloadFileCardProps) {
  const { url, fileName: propFileName, className, style } = props;
  const [previewOpen, setPreviewOpen] = useState(false);

  // Extract filename from URL if not provided
  const fileName = useMemo(() => {
    if (propFileName) return propFileName;
    try {
      const urlObj = new URL(url);
      const pathname = urlObj.pathname;
      const parts = pathname.split("/");
      return parts[parts.length - 1] || "未知文件";
    } catch {
      return "未知文件";
    }
  }, [url, propFileName]);

  const { icon } = useMemo(() => getFileIcon(fileName), [fileName]);

  // Split filename for display
  const [namePrefix, nameSuffix] = useMemo(() => {
    const match = fileName.match(/^(.*)\.[^.]+$/);
    return match ? [match[1], fileName.slice(match[1].length)] : [fileName, ""];
  }, [fileName]);

  const fileType = useMemo(() => getFileType(fileName), [fileName]);

  const handlePreview = () => {
    setPreviewOpen(true);
  };

  const handleDownload = (e: React.MouseEvent) => {
    e.stopPropagation(); // 阻止事件冒泡，避免打开弹窗
    const link = document.createElement("a");
    link.href = url;
    link.download = fileName;
    link.target = "_blank";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // 合并样式
  const mergedCardStyle = {
    ...cardStyle,
    borderColor: "#d9d9d9",
    ...style,
  };

  const mergedHintStyle = {
    ...hintStyle,
    color: fileType === "image" ? "#1677ff" : fileType === "video" ? "#faad14" : fileType === "office" ? "#1677ff" : fileType === "pdf" ? "#ff4d4f" : fileType === "markdown" ? "#52c41a" : fileType === "text" ? "#52c41a" : fileType === "html" ? "#722ed1" : "#8c8c8c",
  };

  // 根据文件类型显示不同的提示
  const hintText = useMemo(() => {
    switch (fileType) {
      case "image":
        return "图片";
      case "video":
        return "视频";
      case "audio":
        return "音频";
      case "office":
        return "Office";
      case "pdf":
        return "PDF";
      case "markdown":
        return "Markdown";
      case "text":
        return "文本";
      case "html":
        return "HTML";
      default:
        return "文件";
    }
  }, [fileType]);

  return (
    <>
      <div
        className={className}
        style={mergedCardStyle}
        onClick={handlePreview}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            handlePreview();
          }
        }}
      >
        <div style={iconStyle}>
          {icon}
        </div>
        <div style={contentStyle}>
          <div style={nameStyle}>
            {namePrefix || EMPTY}
            {nameSuffix}
          </div>
          <div style={mergedHintStyle}>
            {hintText}
          </div>
        </div>
        {/* 直接下载按钮 */}
        <div
          style={downloadBtnStyle}
          onClick={handleDownload}
          title="下载"
        >
          <SparkDownloadLine style={{ fontSize: "14px" }} />
        </div>
      </div>
      <FilePreviewModal
        open={previewOpen}
        onClose={() => setPreviewOpen(false)}
        fileUrl={url}
        fileName={fileName}
      />
    </>
  );
}

export default DownloadFileCard;