import { createGlobalStyle } from "antd-style";
import { DESIGN_TOKENS } from "@/config/designTokens";

export default createGlobalStyle`
.featured-cases {
  width: 100%;

  &-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
  }

  &-title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    font-weight: 500;
    color: ${DESIGN_TOKENS.colorTextSecondary};
  }

  &-title-icon {
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  &-more {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 13px;
    color: ${DESIGN_TOKENS.colorTextSecondary};
    cursor: pointer;

    &:hover {
      opacity: 0.7;
    }
  }

  &-scroll {
    display: flex;
    gap: ${DESIGN_TOKENS.caseCardGap}px;
    overflow-x: auto;
    overflow-y: hidden;
    padding-bottom: 4px;

    &::-webkit-scrollbar {
      height: 4px;
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

  &-card {
    position: relative;
    flex-shrink: 0;
    width: ${DESIGN_TOKENS.caseCardWidth}px;
    height: ${DESIGN_TOKENS.caseCardHeight}px;
    background-color: ${DESIGN_TOKENS.colorBgCard};
    border-radius: 8px;
    overflow: hidden;
    cursor: pointer;
    display: flex;
    // flex:1;
    flex-direction: column;
    transition: box-shadow 0.2s ease;

    &:hover {
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
    }
  }

  &-card-image {
    width: 100%;
    height: 53px;
    object-fit: cover;
    background-color: #f0f0f0;
    flex-shrink: 0;
  }

  &-card-text {
    flex: 1;
    padding: 8px 16px;
    font-size: 12px;
    line-height: 18px;
    color: ${DESIGN_TOKENS.colorTextSecondary};
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 5;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  /* Hover overlay */
  &-card:hover &-overlay {
    opacity: 1;
    pointer-events: auto;
  }

  &-overlay {
    position: absolute;
    inset: 0;
    background-color: rgba(0, 0, 0, 0.6);
    border-radius: 8px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 13px;
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.2s ease;
    z-index: 1;
  }

  &-overlay-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    width: 88px;
    height: 30px;
    border-radius: ${DESIGN_TOKENS.radiusButtonPill}px;
    background-color: ${DESIGN_TOKENS.colorPrimary};
    color: #FFFFFF;
    font-size: 13px;
    border: none;
    cursor: pointer;
    outline: none;
    transition: opacity 0.15s ease;

    &:hover {
      opacity: 0.85;
    }
  }

  &-overlay-btn-icon {
    width: 16px;
    height: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
  }
}
`;
