import React, { useState, useCallback, useRef } from "react";
import { Input, Upload } from "antd";
import { SparkAttachmentLine } from "@agentscope-ai/icons";
import { IconButton } from "@agentscope-ai/design";
import { Tooltip } from "antd";
import Style from "./style";
import KnowledgeTabs from "../KnowledgeTabs";
import FeaturedCases, { type FeaturedCase } from "../FeaturedCases";
import CaseDetailDrawer, { type CaseDetailData } from "../CaseDetailDrawer";
import { DESIGN_TOKENS } from "@/config/designTokens";

interface WelcomeCenterLayoutProps {
  greeting?: string;
  prompts?: {
    label?: string;
    value: string;
    icon?: React.ReactElement;
    image?: string;
  }[];
  onSubmit: (data: { query: string }) => void;
}

function SendIcon() {
  return (
    <svg width="16" height="17" viewBox="0 0 16 17" fill="none">
      <path
        d="M3.04 7.19L6.56 10.71L12.96 4.31"
        stroke="white"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function WelcomeCenterLayout(props: WelcomeCenterLayoutProps) {
  const {
    greeting = "你好，你的专属小龙虾，前来报到！",
    prompts,
    onSubmit,
  } = props;
  const [inputValue, setInputValue] = useState("");
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [selectedCase, setSelectedCase] = useState<CaseDetailData | null>(null);
  const uploadRef = useRef<any>(null);

  const handleSend = useCallback(() => {
    const trimmed = inputValue.trim();
    if (!trimmed) return;
    onSubmit({ query: trimmed });
    setInputValue("");
  }, [inputValue, onSubmit]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  const handleFillInput = useCallback((text: string) => {
    setInputValue(text);
  }, []);

  const handleViewCase = useCallback((caseItem: FeaturedCase) => {
    setSelectedCase({
      title: caseItem.label,
      value: caseItem.value,
    });
    setDrawerVisible(true);
  }, []);

  const cases: FeaturedCase[] = (prompts || []).map((p) => ({
    label: p.label || p.value,
    value: p.value,
    image: p.image,
  }));

  return (
    <>
      <Style />
      <div className="welcome-center-layout">
        {/* Greeting */}
        <div className="welcome-greeting">{greeting}</div>

        {/* Input Card */}
        <div className="welcome-input-card">
          <Input.TextArea
            className="welcome-input-placeholder"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="任何要求，尽管提…"
            autoSize={{ minRows: 1, maxRows: 5 }}
            bordered={false}
          />
          <div className="welcome-input-actions">
            <div className="welcome-input-actions-left">
              <Tooltip title="上传附件">
                <div>
                  <Upload
                    ref={uploadRef}
                    showUploadList={false}
                    accept="*/*"
                    beforeUpload={(file) => {
                      document.dispatchEvent(
                        new CustomEvent("pasteFile", {
                          detail: { file },
                        }),
                      );
                      return false;
                    }}
                  >
                    <IconButton
                      icon={<SparkAttachmentLine />}
                      bordered={false}
                    />
                  </Upload>
                </div>
              </Tooltip>
            </div>
            <button
              className="welcome-input-send-btn"
              onClick={handleSend}
              disabled={!inputValue.trim()}
              type="button"
            >
              <SendIcon />
            </button>
          </div>
        </div>

        {/* Knowledge Tabs */}
        <div className="welcome-tabs-area">
          <KnowledgeTabs />
        </div>

        {/* Featured Cases */}
        <div className="welcome-cases-area">
          <FeaturedCases
            cases={cases}
            onFillInput={handleFillInput}
            onViewCase={handleViewCase}
          />
        </div>
      </div>

      {/* Case Detail Drawer */}
      <CaseDetailDrawer
        visible={drawerVisible}
        onClose={() => setDrawerVisible(false)}
        caseData={selectedCase}
        onMakeSimilar={(value) => {
          setInputValue(value);
        }}
      />
    </>
  );
}
