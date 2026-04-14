import { useCallback, useEffect } from "react";
import { useProviderContext, ChatInput, Disclaimer } from '@/components/agentscope-chat';
import { useChatAnywhereOptions } from "../../Context/ChatAnywhereOptionsContext";
import { useGetState } from 'ahooks';
import { useChatAnywhereInput } from "../../Context/ChatAnywhereInputContext";
import useAttachments from "./useAttachments";
import { IAgentScopeRuntimeWebUIInputData } from '@/components/agentscope-chat';
import { emit } from '../../Context/useChatAnywhereEventEmitter';

export interface InputProps {
  onCancel: () => void;
  onSubmit: (data: IAgentScopeRuntimeWebUIInputData) => void;
}

export default function Input(props: InputProps) {
  const [content, setContent, getContent] = useGetState('');
  const prefixCls = useProviderContext().getPrefixCls('chat-anywhere-input');
  const senderOptions = useChatAnywhereOptions(v => v.sender);
  const inputContext = useChatAnywhereInput(v => v);

  const {
    placeholder = '',
    disclaimer = '',
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
    uploadFileListHeader
  } = useAttachments(attachments, { disabled: !!inputContext.disabled });

  // Listen for external pasteFile events (drag-drop upload)
  useEffect(() => {
    const handler = (e: Event) => {
      const file = (e as CustomEvent).detail?.file as File | undefined;
      if (file && handlePasteFile) {
        handlePasteFile(file);
      }
    };
    document.addEventListener('pasteFile', handler);
    return () => document.removeEventListener('pasteFile', handler);
  }, [handlePasteFile]);

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
        placeholder={placeholder}
        value={content}
        prefix={<>
          {uploadIconButton}
          {prefix}
        </>}
        header={uploadFileListHeader}
        onChange={setContent}
        maxLength={maxLength}
        onSubmit={handleSubmit}
        onCancel={handleCancel}
        allowSpeech={allowSpeech}
        onPasteFile={handlePasteFile}
        suggestions={suggestions}
      />
      {afterUI}
    </div>
    {
      disclaimer ? <Disclaimer desc={disclaimer} /> : <div className={`${prefixCls}-blank`}></div>
    }
  </div>;
}