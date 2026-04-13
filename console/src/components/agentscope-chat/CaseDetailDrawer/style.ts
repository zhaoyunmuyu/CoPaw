import { createGlobalStyle } from 'antd-style';
import { DESIGN_TOKENS } from '@/config/designTokens';

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

.case-detail-drawer-body {
  display: flex;
  gap: 16px;
  padding: 16px 20px;
  overflow: auto;
  height: calc(100% - 48px - 60px);
}

.case-detail-drawer-table-panel {
  flex: 3;
  background: ${DESIGN_TOKENS.colorBgCard};
  border-radius: ${DESIGN_TOKENS.radiusPanel}px;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.case-detail-drawer-table-title {
  font-size: 14px;
  font-weight: 500;
  color: ${DESIGN_TOKENS.colorTextPrimary};
  margin-bottom: 12px;
  line-height: 21px;
}

.case-detail-drawer-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
  line-height: 22px;
}

.case-detail-drawer-table thead th {
  background: #f7f7fc;
  color: ${DESIGN_TOKENS.colorTextPrimary};
  font-weight: 500;
  text-align: left;
  padding: 9px 16px;
  white-space: nowrap;
}

.case-detail-drawer-table tbody td {
  padding: 9px 16px;
  color: ${DESIGN_TOKENS.colorTextPrimary};
  border-top: 1px solid rgba(0, 0, 0, 0.04);
  vertical-align: top;
}

.case-detail-drawer-table tbody tr:hover {
  background: rgba(0, 0, 0, 0.02);
}

.case-detail-drawer-table-action {
  color: ${DESIGN_TOKENS.colorPrimary};
  cursor: pointer;
  display: block;
  line-height: 22px;

  &:hover {
    opacity: 0.8;
  }
}

.case-detail-drawer-steps-panel {
  flex: 2;
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
}

.case-detail-drawer-footer-btn--primary {
  background: ${DESIGN_TOKENS.colorPrimary};
  color: #FFFFFF;
  border-color: ${DESIGN_TOKENS.colorPrimary};
}
`;
