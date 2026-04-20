import React from "react";
import {
  xlsxIcon,
  imgIcon,
  mdIcon,
  pdfIcon,
  pptIcon,
  docIcon,
  zipIcon,
  videoIcon,
  audioIcon,
} from "@/assets/icons";

// File extension groups
export const IMG_EXTS = ["png", "jpg", "jpeg", "gif", "bmp", "webp", "svg"];
export const VIDEO_EXTS = ["mp4", "avi", "mov", "wmv", "flv", "mkv", "webm"];
export const AUDIO_EXTS = ["mp3", "wav", "flac", "ape", "aac", "ogg", "m4a"];
export const OFFICE_EXTS = ["doc", "docx", "xls", "xlsx", "ppt", "pptx"];
export const PDF_EXTS = ["pdf"];
export const MD_EXTS = ["md", "mdx"];
// 常见文本类型
export const TEXT_EXTS = ["txt", "json", "xml", "csv", "log", "yaml", "yml", "toml", "ini", "conf", "config", "env", "sh", "bash", "zsh", "ps1", "bat", "cmd"];
// HTML 类型
export const HTML_EXTS = ["html", "htm", "xhtml"];

const DEFAULT_ICON_COLOR = "#8c8c8c";

const IconImage = ({ url, size = 24 }: { url: string; size?: number }) => (
  <img src={url} width={size} height={size} alt="file icon" style={{ objectFit: "contain" }} />
);

// File icon mapping for card display (smaller icons)
const PRESET_FILE_ICONS: {
  ext: string[];
  color: string;
  icon: React.ReactElement;
}[] = [
  { icon: <IconImage url={xlsxIcon} />, color: "#22b35e", ext: ["xlsx", "xls"] },
  { icon: <IconImage url={imgIcon} />, color: DEFAULT_ICON_COLOR, ext: IMG_EXTS },
  { icon: <IconImage url={mdIcon} />, color: DEFAULT_ICON_COLOR, ext: ["md", "mdx"] },
  { icon: <IconImage url={pdfIcon} />, color: "#ff4d4f", ext: ["pdf"] },
  { icon: <IconImage url={pptIcon} />, color: "#ff6e31", ext: ["ppt", "pptx"] },
  { icon: <IconImage url={docIcon} />, color: "#1677ff", ext: ["doc", "docx"] },
  { icon: <IconImage url={zipIcon} />, color: "#fab714", ext: ["zip", "rar", "7z", "tar", "gz"] },
  { icon: <IconImage url={videoIcon} />, color: "#ff4d4f", ext: VIDEO_EXTS },
  { icon: <IconImage url={audioIcon} />, color: "#8c8c8c", ext: AUDIO_EXTS },
];

function getExtension(fileName: string): string {
  const parts = fileName.split(".");
  return parts.length > 1 ? parts[parts.length - 1].toLowerCase() : "";
}

function matchExt(suffix: string, ext: string[]): boolean {
  const lowerSuffix = `.${suffix}`;
  return ext.some((e) => lowerSuffix.toLowerCase() === `.${e}`);
}

export type FileType = "image" | "video" | "audio" | "office" | "pdf" | "markdown" | "text" | "html" | "other";

export function getFileType(fileName: string): FileType {
  const ext = getExtension(fileName);
  if (matchExt(ext, IMG_EXTS)) return "image";
  if (matchExt(ext, VIDEO_EXTS)) return "video";
  if (matchExt(ext, AUDIO_EXTS)) return "audio";
  if (matchExt(ext, OFFICE_EXTS)) return "office";
  if (matchExt(ext, PDF_EXTS)) return "pdf";
  if (matchExt(ext, MD_EXTS)) return "markdown";
  if (matchExt(ext, HTML_EXTS)) return "html";
  if (matchExt(ext, TEXT_EXTS)) return "text";
  return "other";
}

export function isOfficeFile(fileName: string): boolean {
  const ext = getExtension(fileName);
  return matchExt(ext, OFFICE_EXTS);
}

/**
 * 获取 Office 文件预览 URL
 * 使用 Microsoft Office Online Viewer
 */
export function getOfficePreviewUrl(fileUrl: string): string {
  // Microsoft Office Online Viewer 需要 URL 是公开可访问的
  // 格式: https://view.officeapps.live.com/op/embed.aspx?src=FILE_URL
  return `https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(fileUrl)}`;
}

export function getFileIcon(fileName: string, size = 24): { icon: React.ReactElement; color: string } {
  const ext = getExtension(fileName);

  for (const { ext: extensions, color } of PRESET_FILE_ICONS) {
    if (matchExt(ext, extensions)) {
      // 动态根据 ext 找到对应图标 URL
      const iconUrl = getIconUrlByExt(extensions[0]);
      return { icon: <IconImage url={iconUrl} size={size} />, color };
    }
  }

  // Default fallback - use zip icon
  return {
    icon: <IconImage url={zipIcon} size={size} />,
    color: DEFAULT_ICON_COLOR,
  };
}

// 根据 ext 返回图标 URL
function getIconUrlByExt(ext: string): string {
  const extToIcon: Record<string, string> = {
    xlsx: xlsxIcon, xls: xlsxIcon,
    png: imgIcon, jpg: imgIcon, jpeg: imgIcon, gif: imgIcon, bmp: imgIcon, webp: imgIcon, svg: imgIcon,
    md: mdIcon, mdx: mdIcon,
    pdf: pdfIcon,
    ppt: pptIcon, pptx: pptIcon,
    doc: docIcon, docx: docIcon,
    zip: zipIcon, rar: zipIcon, "7z": zipIcon, tar: zipIcon, gz: zipIcon,
    mp4: videoIcon, avi: videoIcon, mov: videoIcon, wmv: videoIcon, flv: videoIcon, mkv: videoIcon, webm: videoIcon,
    mp3: audioIcon, wav: audioIcon, flac: audioIcon, ape: audioIcon, aac: audioIcon, ogg: audioIcon, m4a: audioIcon,
    // 文本类型使用 md 图标
    txt: mdIcon, json: mdIcon, xml: mdIcon, csv: mdIcon, log: mdIcon,
    yaml: mdIcon, yml: mdIcon, toml: mdIcon, ini: mdIcon, conf: mdIcon, config: mdIcon, env: mdIcon,
    sh: mdIcon, bash: mdIcon, zsh: mdIcon, ps1: mdIcon, bat: mdIcon, cmd: mdIcon,
    // HTML 类型使用 md 图标
    html: mdIcon, htm: mdIcon, xhtml: mdIcon,
  };
  return extToIcon[ext] || zipIcon;
}