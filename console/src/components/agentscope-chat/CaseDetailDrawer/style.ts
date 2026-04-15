import { createGlobalStyle } from "antd-style";
import { DESIGN_TOKENS } from "@/config/designTokens";

export default createGlobalStyle`
.case-detail-drawer {
  .ant-drawer-content {
    background: transparent !important;
  }

  .ant-drawer-body {
    padding: 0 !important;
    overflow: hidden;
  }
}

.case-detail-drawer-header {
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  background: ${DESIGN_TOKENS.colorBgCard};
  border-bottom: 1px solid #dddddd;
}

.case-detail-drawer-title {
  font-size: 16px;
  font-weight: 500;
  color: ${DESIGN_TOKENS.colorTextDark};
  line-height: 48px;
}

.case-detail-drawer-close {
  width: 16px;
  height: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  padding: 0;
}

.case-detail-drawer-loading-body {
  display: flex;
  align-items: center;
  justify-content: center;
  height: calc(100% - 48px - 60px);
}

.case-detail-drawer-body {
  display: flex;
  gap: 16px;
  padding: 16px 20px;
  overflow: hidden;
  height: calc(100% - 48px - 60px);
}

/* Left panel: Steps (flex: 1) */
.case-detail-drawer-steps-panel {
  flex: 1;
  min-width: 300px;
  background: ${DESIGN_TOKENS.colorBgCard};
  border-radius: ${DESIGN_TOKENS.radiusPanel}px;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow: auto;
}

.case-detail-drawer-step {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.case-detail-drawer-step-title {
  font-size: 14px;
  font-weight: 500;
  color: ${DESIGN_TOKENS.colorTextPrimary};
  line-height: 22px;
}

.case-detail-drawer-step-content {
  font-size: 14px;
  color: ${DESIGN_TOKENS.colorTextPrimary};
  line-height: 22px;
  white-space: pre-wrap;
}

.case-detail-drawer-empty {
  font-size: 14px;
  color: ${DESIGN_TOKENS.colorTextSecondary};
  text-align: center;
  padding: 40px 0;
}

/* Right panel: iframe (flex: 2) */
.case-detail-drawer-iframe-panel {
  flex: 2;
  min-width: 400px;
  background: ${DESIGN_TOKENS.colorBgCard};
  border-radius: ${DESIGN_TOKENS.radiusPanel}px;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.case-detail-drawer-iframe-title {
  font-size: 14px;
  font-weight: 500;
  color: ${DESIGN_TOKENS.colorTextPrimary};
  margin-bottom: 12px;
  line-height: 21px;
}

.case-detail-drawer-iframe-container {
  flex: 1;
  position: relative;
  overflow: hidden;
  border-radius: 4px;
  background: #f7f7fc;
}

.case-detail-drawer-iframe {
  width: 100%;
  height: 100%;
  border: none;
  display: block;
}

.case-detail-drawer-iframe-loading {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  background: #f7f7fc;
  font-size: 14px;
  color: ${DESIGN_TOKENS.colorTextSecondary};
}

.case-detail-drawer-iframe-error {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  background: #f7f7fc;
  font-size: 14px;
  color: ${DESIGN_TOKENS.colorTextSecondary};
}

.case-detail-drawer-iframe-refresh {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border: 1px solid ${DESIGN_TOKENS.colorPrimary};
  border-radius: 4px;
  background: transparent;
  color: ${DESIGN_TOKENS.colorPrimary};
  font-size: 14px;
  cursor: pointer;

  &:hover {
    opacity: 0.85;
  }
}

.case-detail-drawer-iframe-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  font-size: 14px;
  color: ${DESIGN_TOKENS.colorTextSecondary};
}

/* Footer */
.case-detail-drawer-footer {
  height: 60px;
  display: flex;
  align-items: center;
  padding: 0 20px;
  background: ${DESIGN_TOKENS.colorBgCard};
  border-top: 1px solid rgba(0, 0, 0, 0.06);
  gap: 20px;
}

.case-detail-drawer-footer-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 34px;
  border-radius: 24px;
  border: 1px solid ${DESIGN_TOKENS.colorPrimary};
  background: ${DESIGN_TOKENS.colorBgCard};
  color: ${DESIGN_TOKENS.colorPrimary};
  font-size: 14px;
  padding: 0 20px;
  cursor: pointer;
  transition: opacity 0.15s ease;

  &:hover {
    opacity: 0.85;
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.case-detail-drawer-footer-btn--primary {
  background: ${DESIGN_TOKENS.colorPrimary};
  color: #FFFFFF;
  border-color: ${DESIGN_TOKENS.colorPrimary};
}
`;