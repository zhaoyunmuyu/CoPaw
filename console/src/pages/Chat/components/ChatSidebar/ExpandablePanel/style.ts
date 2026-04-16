import { createGlobalStyle } from "antd-style";
import { DESIGN_TOKENS } from "@/config/designTokens";

export default createGlobalStyle`
.expandable-panel {
  position: absolute;
  top: 0;
  left: ${DESIGN_TOKENS.toolbarWidth + DESIGN_TOKENS.panelGap}px;
  width: ${DESIGN_TOKENS.sidebarWidth}px;
  max-height: 100%;
  background-color: ${DESIGN_TOKENS.colorBgCard};
  border-radius: ${DESIGN_TOKENS.radiusPanel}px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.08);
  z-index: 100;
  overflow-y: auto;
  overflow-x: hidden;
  display: flex;
  flex-direction: column;
  padding: ${DESIGN_TOKENS.panelPadding}px;
  animation: panelSlideIn 0.15s ease-out;

  &::-webkit-scrollbar {
    width: 4px;
  }

  &::-webkit-scrollbar-track {
    background: transparent;
  }

  &::-webkit-scrollbar-thumb {
    background: rgba(0, 0, 0, 0.12);
    border-radius: 4px;
  }

  &::-webkit-scrollbar-thumb:hover {
    background: rgba(0, 0, 0, 0.28);
  }

  scrollbar-width: thin;
  scrollbar-color: rgba(0, 0, 0, 0.12) transparent;
}

@keyframes panelSlideIn {
  from {
    opacity: 0;
    transform: translateX(-8px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.expandable-panel-header {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 12px;
  flex-shrink: 0;
}

.expandable-panel-header-title {
  font-size: 16px;
  font-weight: 600;
  font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
  color: ${DESIGN_TOKENS.colorTextPrimary};
  line-height: 21px;
}

.expandable-panel-content {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

/* ─── Task card styles ─── */
.expandable-panel-task-card {
  padding: ${DESIGN_TOKENS.panelTaskCardPadding}px;
  border: 0.5px solid ${DESIGN_TOKENS.colorCardBorder};
  border-radius: ${DESIGN_TOKENS.radiusPanel}px;
  cursor: pointer;
  transition: background-color 0.15s ease;

  &:hover {
    background-color: rgba(0, 0, 0, 0.02);
  }

  & + & {
    margin-top: ${DESIGN_TOKENS.panelTaskCardGap}px;
  }
}

.expandable-panel-task-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}

.expandable-panel-task-title {
  font-size: 16px;
  font-weight: 400;
  font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
  color: ${DESIGN_TOKENS.colorTextPrimary};
  line-height: 21px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  min-width: 0;
}

.expandable-panel-task-badge {
  flex-shrink: 0;
  min-width: 14px;
  height: 14px;
  padding: 0 4px;
  border-radius: ${DESIGN_TOKENS.radiusBadge}px;
  background-color: ${DESIGN_TOKENS.colorBadgeRed};
  color: #FFFFFF;
  font-size: ${DESIGN_TOKENS.badgeFontSize}px;
  font-family: "PingFang SC", sans-serif;
  line-height: 14px;
  text-align: center;
}

.expandable-panel-task-subtitle {
  font-size: 12px;
  font-weight: 400;
  font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
  color: ${DESIGN_TOKENS.colorTextMuted};
  line-height: 16px;
  margin-top: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.expandable-panel-task-time {
  margin-right: 8px;
  color: ${DESIGN_TOKENS.colorTextMuted};
}

/* ─── History row styles ─── */
.expandable-panel-history-item {
  padding: 10px 0;
  cursor: pointer;
  transition: background-color 0.15s ease;

  &:hover {
    background-color: rgba(0, 0, 0, 0.02);
  }

  & + & {
    /* no extra gap */
  }
}

.expandable-panel-history-title {
  font-size: 16px;
  font-weight: 400;
  font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
  color: ${DESIGN_TOKENS.colorTextSecondary};
  line-height: 21px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.expandable-panel-history-time {
  font-size: 12px;
  font-weight: 400;
  font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
  color: ${DESIGN_TOKENS.colorTextMuted};
  line-height: 16px;
  margin-top: 2px;
}

.expandable-panel-empty {
  padding: 24px 0;
  text-align: center;
  color: ${DESIGN_TOKENS.colorTextMuted};
  font-size: 13px;
}
`;
