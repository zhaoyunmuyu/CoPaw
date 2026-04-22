import { createGlobalStyle } from "antd-style";
import { DESIGN_TOKENS } from "@/config/designTokens";

export default createGlobalStyle`
/* ─── Wrapper: contains sidebar + collapse toggle ─── */
.chat-sidebar-wrapper {
  position: relative;
  flex-shrink: 0;
  display: flex;
  flex-direction: row;
  height: 100%;
}

.chat-sidebar-wrapper--collapsed {
  /* When collapsed, only the 64px toolbar shows */
}

/* ─── Collapse toggle button ─── */
.chat-sidebar-collapse-toggle {
  position: absolute;
  right: -13px;
  top: 50%;
  transform: translateY(-50%);
  z-index: 50;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: #FFFFFF;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1);
  transition: all 0.2s ease;

  svg {
    transition: transform 0.2s ease;
  }

  &:hover {
    border-color: ${DESIGN_TOKENS.colorPrimary};
    box-shadow: 0 2px 8px rgba(55, 105, 252, 0.2);

    svg path {
      stroke: ${DESIGN_TOKENS.colorPrimary};
    }
  }
}

/* ─── Expanded sidebar ─── */
.chat-sidebar {
  width: ${DESIGN_TOKENS.sidebarWidth}px;
  height: 100%;
  background-color: ${DESIGN_TOKENS.colorBgSidebar};
  display: flex;
  flex-direction: column;
  border-right: 1px solid rgba(0, 0, 0, 0.06);
  overflow: hidden;
}

.chat-sidebar-content {
  flex: 1;
  overflow-y: auto;
  padding-top: 12px;

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

.chat-sidebar-content-record-list {
  height: calc(100vh - 143px);
  overflow: auto;
  scrollbar-width: thin;
  scrollbar-color: rgba(0, 0, 0, 0.12) transparent;
}

/* History section */
.chat-sidebar-history {
  padding: 0 20px;

  &-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 21px;
    margin-bottom: 12px;
    cursor: pointer;
  }

  &-title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    font-weight: 500;
    color: ${DESIGN_TOKENS.colorTextPrimary};
  }

  &-toggle {
    width: 16px;
    height: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: transform 0.2s ease;

    &--collapsed {
      transform: rotate(-90deg);
    }
  }

  &-item {
    padding: 10px 0;
    cursor: pointer;
    border-bottom: 1px solid rgba(0, 0, 0, 0.04);

    &:last-child {
      border-bottom: none;
    }

    &:hover {
      background-color: rgba(0, 0, 0, 0.02);
    }
  }

  &-item-title {
    font-size: 14px;
    line-height: 21px;
    color: ${DESIGN_TOKENS.colorTextSecondary};
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  &-item-time {
    font-size: 12px;
    line-height: 16px;
    color: ${DESIGN_TOKENS.colorTextMuted};
    margin-top: 2px;
  }
}

/* New topic button */
.chat-sidebar-new-topic {
  padding: 12px 20px;
}

.chat-sidebar-new-topic-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 228px;
  height: 34px;
  border-radius: ${DESIGN_TOKENS.radiusButtonPill}px;
  background-color: ${DESIGN_TOKENS.colorPrimary};
  color: #FFFFFF;
  font-size: 14px;
  font-weight: 500;
  border: none;
  cursor: pointer;
  outline: none;
  transition: opacity 0.15s ease;

  &:hover {
    opacity: 0.85;
  }
}

/* Footer toolbar */
.chat-sidebar-footer {
  flex-shrink: 0;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 28px;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
  background-color: ${DESIGN_TOKENS.colorBgSidebar};
}

.chat-sidebar-footer-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: ${DESIGN_TOKENS.colorTextPrimary};
  cursor: pointer;

  &:hover {
    opacity: 0.7;
  }
}

.chat-sidebar-footer-divider {
  width: 1px;
  height: 19px;
  background-color: #D7D7DD;
  margin: 0 24px;
}

/* Virtual scrolling history list container */
.chat-sidebar-history-list {
  flex: 1;
  min-height: 100px;
  // max-height: 400px;
  // overflow-y: auto;

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

/* Skeleton styles */
.chat-sidebar-history-skeleton-item {
  height: 48px;
  padding: 10px 12px;
  margin-bottom: 4px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.chat-sidebar-history-skeleton-title {
  height: 20px;
  width: 60%;
  background: linear-gradient(90deg, #f0f0f0 25%, #e8e8e8 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: skeleton-shimmer 1.5s infinite;
  border-radius: 4px;
}

.chat-sidebar-history-skeleton-time {
  height: 14px;
  width: 40%;
  background: linear-gradient(90deg, #f0f0f0 25%, #e8e8e8 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: skeleton-shimmer 1.5s infinite;
  border-radius: 4px;
}

@keyframes skeleton-shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}

/* Empty state */
.chat-sidebar-history-empty {
  padding: 20px;
  text-align: center;
  color: ${DESIGN_TOKENS.colorTextMuted};
  font-size: 14px;
}
`;
