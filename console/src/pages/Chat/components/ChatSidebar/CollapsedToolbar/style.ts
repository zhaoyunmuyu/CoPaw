import { createGlobalStyle } from 'antd-style';
import { DESIGN_TOKENS } from '@/config/designTokens';

export default createGlobalStyle`
.collapsed-toolbar {
  width: ${DESIGN_TOKENS.toolbarWidth}px;
  height: 100%;
  background-color: ${DESIGN_TOKENS.colorBgCard};
  display: flex;
  flex-direction: column;
  align-items: center;
  border-right: 1px solid ${DESIGN_TOKENS.colorCardBorder};
  box-shadow: 1px 0 12px rgba(0, 0, 0, 0.05);
  position: relative;
  flex-shrink: 0;
}

.collapsed-toolbar-icons {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: ${DESIGN_TOKENS.toolbarIconGap}px;
  padding-top: ${DESIGN_TOKENS.toolbarIconPaddingTop}px;
  padding-left: ${DESIGN_TOKENS.toolbarIconPaddingLeft}px;
  padding-right: ${DESIGN_TOKENS.toolbarIconPaddingLeft}px;
}

.collapsed-toolbar-icon-btn {
  width: ${DESIGN_TOKENS.toolbarIconSize}px;
  height: ${DESIGN_TOKENS.toolbarIconSize}px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  border: none;
  background: transparent;
  padding: 0;
  position: relative;
  transition: opacity 0.15s ease;
  border-radius: 6px;

  &:hover {
    background-color: rgba(0, 0, 0, 0.04);
  }
}

.collapsed-toolbar-badge {
  position: absolute;
  top: -4px;
  right: -6px;
  min-width: 14px;
  height: 14px;
  padding: 0 4px;
  border-radius: ${DESIGN_TOKENS.radiusBadge}px;
  background-color: ${DESIGN_TOKENS.colorBadgeRed};
  color: #FFFFFF;
  font-size: ${DESIGN_TOKENS.badgeFontSize}px;
  line-height: 14px;
  text-align: center;
  font-family: "PingFang SC", sans-serif;
  font-weight: 400;
  pointer-events: none;
}

/* Tooltip override for collapsed toolbar */
.collapsed-toolbar .swe-tooltip-inner,
.collapsed-toolbar .ant-tooltip-inner {
  background-color: ${DESIGN_TOKENS.colorTooltipBg} !important;
  border-radius: ${DESIGN_TOKENS.radiusTooltip}px !important;
  font-size: 14px !important;
  padding: 8px 12px !important;
}

.collapsed-toolbar .swe-tooltip-arrow::before,
.collapsed-toolbar .ant-tooltip-arrow::before {
  background: ${DESIGN_TOKENS.colorTooltipBg} !important;
}
`;
