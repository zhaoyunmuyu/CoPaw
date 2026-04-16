import { createGlobalStyle } from "antd-style";
import { DESIGN_TOKENS } from "@/config/designTokens";

export default createGlobalStyle`
.knowledge-tabs {
  display: flex;
  align-items: center;
  gap: 16px;

  &-item {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    height: 28px;
    padding: 4px 8px;
    border-radius: ${DESIGN_TOKENS.radiusTab}px;
    font-size: 12px;
    cursor: pointer;
    white-space: nowrap;
    transition: all 0.2s ease;
    border: none;
    outline: none;

    &--active {
      background-color: ${DESIGN_TOKENS.colorTagPurple};
      color: #FFFFFF;

      .knowledge-tabs-icon {
        color: ${DESIGN_TOKENS.colorTagPurple};
      }
    }

    &--inactive {
      background-color: transparent;
      color: ${DESIGN_TOKENS.colorTextDark};

      .knowledge-tabs-icon {
        color: ${DESIGN_TOKENS.colorTextSecondary};
      }
    }

    &:hover {
      opacity: 0.85;
    }
  }

  &-divider {
    width: 1px;
    height: 14px;
    background-color: ${DESIGN_TOKENS.colorDivider};
  }

  &-icon {
    width: 16px;
    height: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
  }
}
`;
