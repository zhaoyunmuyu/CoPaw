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
    gap: 4px;
  }

  &-item {
    position: relative;
    padding: 10px 12px;
    cursor: pointer;
    border-radius: 4px;
    background-color: transparent;
    transition: background-color 0.15s ease;
    overflow: hidden;

    &:hover {
      background: rgba(55, 105, 252, 0.03);

      .chat-task-list-item-actions {
        opacity: 1;
        pointer-events: auto;
      }
    }

    &--paused {
      background: rgba(223, 146, 33, 0.06);
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
    line-height: 20px;
    font-weight: 500;
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

  &-item-actions {
    position: absolute;
    right: 8px;
    top: 50%;
    transform: translateY(-50%);
    display: flex;
    align-items: center;
    gap: 6px;
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.2s;
  }

  &-item-action {
    flex-shrink: 0;
    height: 24px;
    padding: 0 10px;
    border: none;
    border-radius: 999px;
    background: rgba(55, 105, 252, 0.1);
    color: ${DESIGN_TOKENS.colorPrimary};
    font-size: 12px;
    font-weight: 600;
    line-height: 24px;
    cursor: pointer;
    transition:
      background-color 0.15s ease,
      color 0.15s ease;

    &:hover {
      background: rgba(55, 105, 252, 0.16);
    }

    &--delete {
      background: rgba(254, 40, 66, 0.1);
      color: ${DESIGN_TOKENS.colorBadgeRed};

      &:hover {
        background: rgba(254, 40, 66, 0.16);
      }
    }
  }

  &-item-status {
    margin-bottom: 4px;
    font-size: 12px;
    line-height: 16px;
    font-weight: 600;

    &--auto {
      color: #A15C07;
    }

    &--manual {
      color: ${DESIGN_TOKENS.colorTextMuted};
    }
  }

  &-item-subtitle {
    font-size: 12px;
    line-height: 16px;
    color: ${DESIGN_TOKENS.colorTextMuted};
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  &-item-next-run {
    margin-top: 4px;
    font-size: 12px;
    line-height: 16px;
    color: ${DESIGN_TOKENS.colorTextSecondary};
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