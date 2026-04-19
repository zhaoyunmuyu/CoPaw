import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Modal, Image, message, Tooltip, Spin } from "antd";
import { FullscreenOutlined } from "@ant-design/icons";
import {
  SparkFalseLine,
  SparkDownloadLine,
  SparkCopyLine,
  SparkTrueLine,
} from "@agentscope-ai/icons";
import { IconButton } from "@agentscope-ai/design";
import { Markdown } from "@/components/agentscope-chat";
import { getFileIcon, getFileType, getOfficePreviewUrl } from "./fileUtils";

export interface FilePreviewModalProps {
  open: boolean;
  onClose: () => void;
  fileUrl: string;
  fileName: string;
}

// 文本预览样式
const textPreviewStyle: React.CSSProperties = {
  width: "100%",
  maxHeight: "400px",
  overflow: "auto",
  backgroundColor: "#f5f5f5",
  borderRadius: "8px",
  padding: "12px",
  fontFamily: "monospace",
  fontSize: "12px",
  lineHeight: "1.5",
  whiteSpace: "pre-wrap",
  wordBreak: "break-all",
};

function FilePreviewModal(props: FilePreviewModalProps) {
  const { open, onClose, fileUrl, fileName } = props;
  const [copied, setCopied] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const [textContent, setTextContent] = useState<string | null>(null);
  const [textLoading, setTextLoading] = useState(false);
  const [textError, setTextError] = useState<string | null>(null);

  const fileType = useMemo(() => getFileType(fileName), [fileName]);
  // 弹窗中使用大图标
  const { icon, color } = useMemo(() => getFileIcon(fileName, 48), [fileName]);

  // 加载文本/Markdown 内容
  useEffect(() => {
    if (open && (fileType === "text" || fileType === "markdown") && fileUrl) {
      setTextLoading(true);
      setTextError(null);
      setTextContent(null);

      fetch(fileUrl)
        .then((res) => {
          if (!res.ok) throw new Error("加载失败");
          return res.text();
        })
        .then((text) => {
          // 限制显示长度，避免超长文本
          const maxLength = 50000;
          setTextContent(text.length > maxLength ? text.slice(0, maxLength) + "\n\n... (内容过长，已截断)" : text);
        })
        .catch(() => {
          setTextError("文件暂时无法预览");
        })
        .finally(() => {
          setTextLoading(false);
        });
    }
  }, [open, fileType, fileUrl]);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(fileUrl);
      message.success("链接已复制");
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      message.error("复制失败");
    }
  }, [fileUrl]);

  const handleDownload = useCallback(() => {
    const link = document.createElement("a");
    link.href = fileUrl;
    link.download = fileName;
    link.target = "_blank";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }, [fileUrl, fileName]);

  const handleFullscreen = useCallback(() => {
    setFullscreen((prev) => !prev);
  }, []);

  // 全屏时的内容高度
  const previewHeight = fullscreen ? "85vh" : "500px";

  // Render preview content based on file type
  const renderPreviewContent = useMemo(() => {
    if (fileType === "image") {
      return (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Image
            src={fileUrl}
            alt={fileName}
            style={{ maxWidth: "100%", maxHeight: previewHeight, objectFit: "contain" }}
          />
        </div>
      );
    }

    if (fileType === "video") {
      return (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
          <video
            controls
            style={{ maxWidth: "100%", maxHeight: previewHeight }}
            src={fileUrl}
          >
            <source src={fileUrl} />
          </video>
        </div>
      );
    }

    if (fileType === "audio") {
      return (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: "20px 0" }}>
          <audio controls style={{ width: "100%" }} src={fileUrl}>
            <source src={fileUrl} />
          </audio>
        </div>
      );
    }

    // Office files - use iframe preview
    if (fileType === "office") {
      const previewUrl = getOfficePreviewUrl(fileUrl);
      return (
        <div style={{ width: "100%", height: previewHeight }}>
          <iframe
            src={previewUrl}
            style={{ width: "100%", height: "100%", border: "none" }}
            title="Office Preview"
          />
        </div>
      );
    }

    // PDF files - use iframe preview
    if (fileType === "pdf") {
      return (
        <div style={{ width: "100%", height: previewHeight }}>
          <iframe
            src={fileUrl}
            style={{ width: "100%", height: "100%", border: "none" }}
            title="PDF Preview"
          />
        </div>
      );
    }

    // HTML files - use iframe preview
    if (fileType === "html") {
      return (
        <div style={{ width: "100%", height: previewHeight }}>
          <iframe
            src={fileUrl}
            style={{ width: "100%", height: "100%", border: "none" }}
            title="HTML Preview"
            sandbox="allow-scripts allow-same-origin"
          />
        </div>
      );
    }

    // Markdown files - fetch and render with Markdown component
    if (fileType === "markdown") {
      if (textLoading) {
        return <Spin tip="加载中..." />;
      }
      if (textError) {
        return (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: "24px" }}>
            <div style={{ color: "#8c8c8c", marginBottom: "16px", fontSize: "14px" }}>
              文件暂时无法预览，请尝试下载查看
            </div>
            <IconButton icon={<SparkDownloadLine />} onClick={handleDownload}>
              下载文件查看
            </IconButton>
          </div>
        );
      }
      if (textContent) {
        return (
          <div style={{ width: "100%", maxHeight: previewHeight, overflow: "auto", padding: "12px" }}>
            <Markdown content={textContent} allowHtml />
          </div>
        );
      }
      return null;
    }

    // Text files - fetch and display content
    if (fileType === "text") {
      if (textLoading) {
        return <Spin tip="加载中..." />;
      }
      if (textError) {
        return (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: "24px" }}>
            <div style={{ color: "#8c8c8c", marginBottom: "16px", fontSize: "14px" }}>
              文件暂时无法预览，请尝试下载查看
            </div>
            <IconButton icon={<SparkDownloadLine />} onClick={handleDownload}>
              下载文件查看
            </IconButton>
          </div>
        );
      }
      if (textContent) {
        return (
          <div style={{ ...textPreviewStyle, maxHeight: previewHeight }}>
            <code>{textContent}</code>
          </div>
        );
      }
      return null;
    }

    // Other file types - show file info card
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "24px", textAlign: "center" }}>
        <div style={{ marginBottom: "16px", color }}>
          {icon}
        </div>
        <div style={{ fontSize: "16px", fontWeight: 500, marginBottom: "8px", maxWidth: "300px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {fileName}
        </div>
        <div style={{ fontSize: "12px", color: "#8c8c8c" }}>
          文件类型: {fileName.split(".").pop()?.toUpperCase() || "未知"}
        </div>
        <IconButton
          icon={<SparkDownloadLine />}
          onClick={handleDownload}
          style={{ marginTop: 16 }}
        >
          下载文件
        </IconButton>
      </div>
    );
  }, [fileType, fileUrl, fileName, icon, color, handleDownload, textLoading, textError, textContent, previewHeight]);

  // Header actions
  const headerActions = useMemo(() => {
    const actions = [
      <Tooltip key="copy" title="复制链接">
        <IconButton
          size="small"
          icon={copied ? <SparkTrueLine style={{ color: "#52c41a" }} /> : <SparkCopyLine />}
          onClick={handleCopy}
          bordered={false}
        />
      </Tooltip>,
      <Tooltip key="download" title="下载文件">
        <IconButton
          size="small"
          icon={<SparkDownloadLine />}
          onClick={handleDownload}
          bordered={false}
        />
      </Tooltip>,
    ];

    // 所有支持预览的文件类型都添加全屏按钮
    const previewableTypes = ["image", "video", "audio", "office", "pdf", "markdown", "text", "html"];
    if (previewableTypes.includes(fileType)) {
      actions.unshift(
        <Tooltip key="fullscreen" title={fullscreen ? "退出全屏" : "全屏预览"}>
          <IconButton
            size="small"
            icon={<FullscreenOutlined />}
            onClick={handleFullscreen}
            bordered={false}
          />
        </Tooltip>,
      );
    }

    return actions;
  }, [fileType, handleCopy, handleDownload, handleFullscreen, copied, fullscreen]);

  return (
    <Modal
      open={open}
      onCancel={onClose}
      footer={null}
      width={fullscreen ? "95vw" : 800}
      centered
      closeIcon={
        <IconButton
          size="small"
          icon={<SparkFalseLine />}
          bordered={false}
        />
      }
      title={
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%" }}>
          <span style={{ fontSize: "14px", fontWeight: 500, maxWidth: fullscreen ? "60vw" : "400px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {fileName}
          </span>
          <div style={{ display: "flex", alignItems: "center", gap: "12px", marginRight: "32px" }}>
            {headerActions}
          </div>
        </div>
      }
      styles={{
        content: { padding: "16px 24px" },
        body: { padding: "16px 0" },
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: fullscreen ? "85vh" : "200px" }}>
        {renderPreviewContent}
      </div>
    </Modal>
  );
}

export default FilePreviewModal;