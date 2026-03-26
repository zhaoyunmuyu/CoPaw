import { useCallback, useRef } from "react";
import { useProviderContext, ChatInput, Disclaimer } from '@/chat';
import { useChatAnywhereOptions } from "../../Context/ChatAnywhereOptionsContext";
import { useGetState } from 'ahooks';
import { useChatAnywhereInput } from "../../Context/ChatAnywhereInputContext";
import useAttachments from "./useAttachments";
import { IAgentScopeRuntimeWebUIInputData } from "@/chat";
import { IconButton, message, Tooltip } from "@agentscope-ai/design";
import { SparkUploadLine } from "@agentscope-ai/icons";
import { workspaceApi } from "@/api/modules/workspace";
import { useTranslation } from "react-i18next";

export interface InputProps {
  onCancel: () => void;
  onSubmit: (data: IAgentScopeRuntimeWebUIInputData) => void;
}

export default function Input(props: InputProps) {
  const [content, setContent, getContent] = useGetState('');
  const prefixCls = useProviderContext().getPrefixCls('chat-anywhere-input');
  const senderOptions = useChatAnywhereOptions(v => v.sender);
  const inputContext = useChatAnywhereInput(v => v);
  const { t } = useTranslation();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const {
    placeholder = '',
    disclaimer = '',
    maxLength,
    beforeSubmit = () => Promise.resolve(true),
    beforeUI,
    afterUI,
    scalable = true,
    attachments,
    prefix,
    allowSpeech,
  } = senderOptions || {};

  const {
    getFileList,
    setFileList,
    uploadIconButton,
    uploadFileListHeader
  } = useAttachments(attachments, { disabled: !!inputContext.disabled });

  const handleWorkspaceUpload = useCallback(async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!file.name.toLowerCase().endsWith(".zip")) {
      message.error(t("workspace.zipOnly"));
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      return;
    }

    const maxSize = 100 * 1024 * 1024;
    if (file.size > maxSize) {
      message.error(
        t("workspace.fileSizeExceeded", {
          size: (file.size / (1024 * 1024)).toFixed(2),
        }),
      );
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      return;
    }

    try {
      const result = await workspaceApi.uploadFile(file);
      if (result.success) {
        message.success(t("workspace.uploadSuccess"));
      } else {
        message.error(t("workspace.uploadFailed") + ": " + result.message);
      }
    } catch (error) {
      console.error("Upload failed:", error);
      message.error(
        t("workspace.uploadFailed") + ": " + (error as Error).message,
      );
    } finally {
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  }, [t]);


  const handleSubmit = useCallback(async () => {
    const next = await beforeSubmit();
    if (!next) return;

    const fileList = (getFileList?.() || []).filter(i => i.response?.url);
    props.onSubmit({ query: getContent(), fileList });
    setContent('');
    setFileList && setFileList([]);
  }, []);

  const handleCancel = useCallback(() => {
    props.onCancel();
  }, []);

  return <div className={prefixCls}>
    <div className={`${prefixCls}-wrapper`}>
      {beforeUI}
      <ChatInput
        loading={inputContext.loading}
        disabled={inputContext.disabled}
        scalable={scalable}
        placeholder={placeholder}
        value={content}
        prefix={<>
          {uploadIconButton}
          <Tooltip title={t("workspace.uploadTooltip") || "上传工作空间文件 (.zip)"}>
            <IconButton
              disabled={!!inputContext.disabled}
              icon={<SparkUploadLine />}
              bordered={false}
              onClick={() => fileInputRef.current?.click()}
            />
          </Tooltip>
          {prefix}
        </>}
        header={uploadFileListHeader}
        onChange={setContent}
        maxLength={maxLength}
        onSubmit={handleSubmit}
        onCancel={handleCancel}
        allowSpeech={allowSpeech}
      />
      {afterUI}
    </div>
    {
      disclaimer ? <Disclaimer desc={disclaimer} /> : <div className={`${prefixCls}-blank`}></div>
    }
    {/* Hidden file input for workspace upload */}
    <input
      type="file"
      ref={fileInputRef}
      onChange={handleWorkspaceUpload}
      style={{ display: "none" }}
      accept=".zip"
      title="Select a ZIP file (max 100MB)"
    />
  </div>;
}