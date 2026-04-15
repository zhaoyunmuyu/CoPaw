import { createGlobalStyle } from "antd-style";
import { DESIGN_TOKENS } from "@/config/designTokens";

export default createGlobalStyle`
.chat-task-list {
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

  &-items {
    display: flex;
    flex-direction: column;
    gap: 0;
  }

  &-item {
    padding: 12px 0;
    cursor: pointer;
    border-bottom: 1px solid rgba(0, 0, 0, 0.04);
    transition: background-color 0.15s ease;

    &:last-child {
      border-bottom: none;
    }

    &:hover {
      background-color: rgba(0, 0, 0, 0.02);
    }
  }

  &-item-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 4px;
  }

  &-item-title {
    font-size: 14px;
    line-height: 21px;
    color: ${DESIGN_TOKENS.colorTextPrimary};
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    flex: 1;
    margin-right: 8px;
  }

  &-item-badge {
    flex-shrink: 0;
    min-width: 14px;
    height: 14px;
    padding: 0 4px;
    border-radius: 7px;
    background-color: ${DESIGN_TOKENS.colorBadgeRed};
    color: #FFFFFF;
    font-size: 10px;
    line-height: 14px;
    text-align: center;
  }

  &-item-subtitle {
    font-size: 12px;
    line-height: 16px;
    color: ${DESIGN_TOKENS.colorTextMuted};
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  &-item-time {
    margin-right: 8px;
    color: ${DESIGN_TOKENS.colorTextMuted};
  }

  &-empty {
    padding: 16px 0;
    text-align: center;
    color: ${DESIGN_TOKENS.colorTextMuted};
    font-size: 13px;
  }
}
`;
