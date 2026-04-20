import React from "react";
import { Space, Card, Typography, Divider, Alert, Tag } from "antd";
import DownloadFileCard from "@/components/agentscope-chat/DownloadFileCard";

const { Title, Paragraph } = Typography;

// 测试用的各种文件类型 URL
const testFiles = [
  // 图片类型 - 使用 httpbin.org（已验证可用）
  { fileName: "sample-image.png", url: "https://httpbin.org/image/png", type: "图片", status: "可用" },
  { fileName: "photo.jpg", url: "https://httpbin.org/image/jpeg", type: "图片", status: "可用" },

  // 视频类型 - 需要本地测试或使用特定 CORS 配置的服务
  { fileName: "demo.mp4", url: "http://localhost:8088/static/test/demo.mp4", type: "视频", status: "本地" },

  // 音频类型 - 需要本地测试
  { fileName: "audio.mp3", url: "http://localhost:8088/static/test/audio.mp3", type: "音频", status: "本地" },

  // PDF - Mozilla PDF.js 示例（已验证可用，支持 iframe 预览）
  { fileName: "document.pdf", url: "https://mozilla.github.io/pdf.js/web/compressed.tracemonkey-pldi-09.pdf", type: "PDF", status: "可用" },

  // Office 文档 - 需要公开 URL 且支持 CORS
  { fileName: "report.docx", url: "http://localhost:8088/static/test/report.docx", type: "Word文档", status: "本地" },
  { fileName: "data.xlsx", url: "http://localhost:8088/static/test/data.xlsx", type: "Excel表格", status: "本地" },
  { fileName: "slides.pptx", url: "http://localhost:8088/static/test/slides.pptx", type: "PPT演示", status: "本地" },

  // Markdown - GitHub raw（已验证可用）
  { fileName: "readme.md", url: "https://raw.githubusercontent.com/markdown-it/markdown-it/master/README.md", type: "Markdown", status: "可用" },

  // HTML - example.com（已验证可用）
  { fileName: "page.html", url: "https://example.com", type: "HTML", status: "可用" },

  // 文本类型 - JSONPlaceholder（已验证可用）
  { fileName: "data.json", url: "https://jsonplaceholder.typicode.com/users", type: "JSON文件", status: "可用" },
  { fileName: "config.txt", url: "https://raw.githubusercontent.com/nicholashagen/node-socketio-chat-app/master/README.md", type: "文本文件", status: "可用" },

  // 压缩文件 - GitHub repo zip（已验证可用）
  { fileName: "archive.zip", url: "https://github.com/nicholashagen/node-socketio-chat-app/archive/refs/heads/master.zip", type: "压缩文件", status: "可用" },

  // 其他/未知类型 - 本地测试
  { fileName: "unknown.xyz", url: "http://localhost:8088/static/test/unknown.xyz", type: "未知类型", status: "本地" },
];

function TestDownloadCardPage() {
  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: "0 auto" }}>
      <Title level={2}>文件下载卡片测试页面</Title>
      <Paragraph>
        此页面测试文件下载卡片的渲染和预览功能。
        点击任意卡片可打开预览弹窗，右侧下载按钮可直接下载。
      </Paragraph>

      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 24 }}
        message="提示"
        description={
          <div>
            <p>测试文件使用公开示例资源或本地文件。各类型文件预览说明：</p>
            <ul style={{ paddingLeft: 20, marginTop: 8 }}>
              <li><Tag color="green">可用</Tag> URL 已验证可访问，预览应正常工作</li>
              <li><Tag color="blue">本地</Tag> 需要本地服务提供文件（见下方说明）</li>
            </ul>
            <p style={{ marginTop: 8 }}>
              <strong>本地测试文件设置：</strong>
              <br />
              将测试文件放到 <code>src/swe/app/static/test/</code> 目录下，
              后端服务会自动提供静态文件访问。
              <br />
              Office 预览限制：Microsoft Office Online Viewer 要求文件 URL 使用 HTTPS 且可公开访问，
              本地测试时建议直接下载查看。
            </p>
          </div>
        }
      />

      <Divider>文件预览测试</Divider>

      <Space direction="vertical" size="large" style={{ width: "100%" }}>
        {Object.entries(
          testFiles.reduce((acc, file) => {
            if (!acc[file.type]) acc[file.type] = [];
            acc[file.type].push(file);
            return acc;
          }, {} as Record<string, typeof testFiles>)
        ).map(([type, files]) => (
          <Card key={type} title={type} size="small">
            <Space wrap align="start">
              {files.map((file) => (
                <div key={file.fileName} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <DownloadFileCard
                    url={file.url}
                    fileName={file.fileName}
                  />
                  <Tag color={file.status === "可用" ? "green" : "blue"}>
                    {file.status}
                  </Tag>
                </div>
              ))}
            </Space>
          </Card>
        ))}
      </Space>
    </div>
  );
}

export default TestDownloadCardPage;