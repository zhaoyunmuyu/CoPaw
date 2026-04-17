import React, { useState, useMemo } from "react";
import { Button, Card, Input, Switch } from "@agentscope-ai/design";
import { CopyOutlined, UndoOutlined, SaveOutlined } from "@ant-design/icons";
import type { MarkdownFile } from "../../../../api/types";
import { XMarkdown } from "@ant-design/x-markdown";
import { useTranslation } from "react-i18next";
import { useAppMessage } from "../../../../hooks/useAppMessage";
import { stripFrontmatter } from "../../../../utils/markdown";
import { copyToClipboard } from "../../../../utils/clipboard";
import styles from "../index.module.less";

interface FileEditorProps {
  selectedFile: MarkdownFile | null;
  fileContent: string;
  loading: boolean;
  hasChanges: boolean;
  onContentChange: (content: string) => void;
  onSave: () => void;
  onReset: () => void;
}

export const FileEditor: React.FC<FileEditorProps> = ({
  selectedFile,
  fileContent,
  loading,
  hasChanges,
  onContentChange,
  onSave,
  onReset,
}) => {
  const { t } = useTranslation();
  const { message } = useAppMessage();
  const [showMarkdown, setShowMarkdown] = useState(true);

  const isMarkdownFile = selectedFile?.filename.endsWith(".md") || false;
  const markdownContent = useMemo(
    () => stripFrontmatter(fileContent || ""),
    [fileContent],
  );

  const handleCopyToClipboard = async () => {
    const success = await copyToClipboard(fileContent);
    if (success) {
      message.success(t("common.copied"));
    } else {
      message.error(t("common.copyFailed"));
    }
  };

  return (
    <div className={styles.fileEditor}>
      <Card className={styles.editorCard}>
        {selectedFile ? (
          <>
            <div className={styles.editorHeader}>
              <div>
                <div className={styles.fileName}>{selectedFile.filename}</div>
                <div className={styles.filePath}>{selectedFile.path}</div>
              </div>
              <div className={styles.buttonGroup}>
                <Button
                  size="small"
                  onClick={onReset}
                  disabled={!hasChanges}
                  icon={<UndoOutlined />}
                >
                  {t("common.reset")}
                </Button>
                <Button
                  type="primary"
                  size="small"
                  onClick={onSave}
                  disabled={!hasChanges}
                  loading={loading}
                  icon={<SaveOutlined />}
                >
                  {t("common.save")}
                </Button>
              </div>
            </div>

            <div className={styles.editorContent}>
              <div className={styles.contentLabel}>
                <div>{t("common.content")}</div>
                {isMarkdownFile && (
                  <div className={styles.buttonGroup}>
                    <div className={styles.markdownToggle}>
                      <span className={styles.toggleLabel}>
                        {t("common.preview")}
                      </span>
                      <Switch
                        checked={showMarkdown}
                        onChange={setShowMarkdown}
                        size="small"
                      />
                    </div>
                    <Button
                      icon={<CopyOutlined />}
                      type="text"
                      onClick={handleCopyToClipboard}
                      className={styles.copyButton}
                    />
                  </div>
                )}
              </div>
              {showMarkdown && isMarkdownFile ? (
                <XMarkdown
                  content={markdownContent}
                  className={styles.markdownViewer}
                />
              ) : (
                <Input.TextArea
                  value={fileContent}
                  onChange={(e) => onContentChange(e.target.value)}
                  className={styles.textarea}
                  placeholder={t("workspace.fileContent")}
                />
              )}
            </div>
          </>
        ) : (
          <div className={styles.emptyState}>{t("workspace.selectFile")}</div>
        )}
        <p className={styles.attribution}>{t("workspace.attribution")}</p>
      </Card>
    </div>
  );
};
