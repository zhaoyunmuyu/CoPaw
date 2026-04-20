import { useCallback, useEffect, useRef } from "react";
import {
  useProviderContext,
  ChatInput,
  Disclaimer,
} from "@/components/agentscope-chat";
import { useChatAnywhereOptions } from "../../Context/ChatAnywhereOptionsContext";
import { useGetState } from "ahooks";
import { useChatAnywhereInput } from "../../Context/ChatAnywhereInputContext";
import useAttachments from "./useAttachments";
import { IAgentScopeRuntimeWebUIInputData } from "@/components/agentscope-chat";
import {
  RUNTIME_INPUT_SET_CONTENT_EVENT,
  type RuntimeInputRestorePayload,
} from "../hooks/followUpSubmit";

export interface InputProps {
  onCancel: () => void;
  onSubmit: (data: IAgentScopeRuntimeWebUIInputData) => void;
}

export default function Input(props: InputProps) {
  const [content, setContent, getContent] = useGetState("");
  const restoredBizParamsRef = useRef<
    IAgentScopeRuntimeWebUIInputData["biz_params"]
  >(undefined);
  const prefixCls = useProviderContext().getPrefixCls("chat-anywhere-input");
  const senderOptions = useChatAnywhereOptions((v) => v.sender);
  const inputContext = useChatAnywhereInput((v) => v);

  const {
    placeholder = "",
    disclaimer = "",
    maxLength,
    beforeSubmit = () => Promise.resolve(true),
    beforeUI,
    afterUI,
    attachments,
    prefix,
    allowSpeech,
    suggestions,
  } = senderOptions || {};

  const {
    getFileList,
    setFileList,
    handlePasteFile,
    uploadIconButton,
    uploadFileListHeader,
  } = useAttachments(attachments, { disabled: !!inputContext.disabled });

  // Listen for external pasteFile events (drag-drop upload)
  useEffect(() => {
    const handler = (e: Event) => {
      const file = (e as CustomEvent).detail?.file as File | undefined;
      if (file && handlePasteFile) {
        handlePasteFile(file);
      }
    };
    document.addEventListener("pasteFile", handler);
    return () => document.removeEventListener("pasteFile", handler);
  }, [handlePasteFile]);

  useEffect(() => {
    const handler = (event: Event) => {
      const detail = (event as CustomEvent<RuntimeInputRestorePayload>).detail;
      const nextContent = detail?.content;
      if (typeof nextContent !== "string") {
        return;
      }

      setContent(nextContent);

      if (Object.prototype.hasOwnProperty.call(detail, "fileList") && setFileList) {
        setFileList(detail.fileList || []);
      }

      if (Object.prototype.hasOwnProperty.call(detail, "biz_params")) {
        restoredBizParamsRef.current = detail.biz_params;
      } else {
        restoredBizParamsRef.current = undefined;
      }
    };

    document.addEventListener(RUNTIME_INPUT_SET_CONTENT_EVENT, handler);
    return () =>
      document.removeEventListener(RUNTIME_INPUT_SET_CONTENT_EVENT, handler);
  }, [setContent, setFileList]);

  const handleContentChange = useCallback(
    (value: string) => {
      restoredBizParamsRef.current = undefined;
      setContent(value);
    },
    [setContent],
  );

  const handleSubmit = useCallback(async () => {
    const next = await beforeSubmit();
    if (!next) return;

    const fileList = (getFileList?.() || []).filter((i) => i.response?.url);
    props.onSubmit({
      query: getContent(),
      fileList,
      biz_params: restoredBizParamsRef.current,
    });
    setContent("");
    restoredBizParamsRef.current = undefined;
    if (setFileList) {
      setFileList([]);
    }
  }, []);

  const handleCancel = useCallback(() => {
    props.onCancel();
  }, []);

  return (
    <div className={prefixCls}>
      <div className={`${prefixCls}-wrapper`}>
        {beforeUI}
        <ChatInput
          loading={inputContext.loading}
          disabled={inputContext.disabled}
          placeholder={placeholder}
          value={content}
          prefix={
            <>
              {uploadIconButton}
              {prefix}
            </>
          }
          header={uploadFileListHeader}
          onChange={handleContentChange}
          maxLength={maxLength}
          onSubmit={handleSubmit}
          onCancel={handleCancel}
          allowSpeech={allowSpeech}
          onPasteFile={handlePasteFile}
          suggestions={suggestions}
        />
        {afterUI}
      </div>
      {disclaimer ? (
        <Disclaimer desc={disclaimer} />
      ) : (
        <div className={`${prefixCls}-blank`}></div>
      )}
    </div>
  );
}
