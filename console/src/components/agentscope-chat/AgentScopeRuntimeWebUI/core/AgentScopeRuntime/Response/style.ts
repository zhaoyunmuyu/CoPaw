import { createGlobalStyle } from "antd-style";

export default createGlobalStyle`
.${(p) => p.theme.prefixCls}-suggestions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 12px;
  padding: 0 4px;

  &-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }

  &-label {
    color: ${({ theme }) => theme.colorTextSecondary};
    font-size: 12px;
    line-height: 18px;
    font-weight: 500;
  }

  &-list {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  &-item {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    background-color: ${({ theme }) => theme.colorFillQuaternary};
    border-radius: 16px;
    cursor: pointer;
    max-width: 400px; // 扩大宽度限制
    transition: background-color 0.2s ease;

    &-text {
      color: ${({ theme }) => theme.colorText};
      font-size: 13px;
      line-height: 20px;
      // 允许换行显示完整内容
      word-break: break-word;
    }

    &-icon {
      width: 14px;
      height: 14px;
      color: ${({ theme }) => theme.colorTextSecondary};
      flex-shrink: 0; // 图标不缩小
    }

    &:hover {
      background-color: ${({ theme }) => theme.colorFillTertiary};
    }

    &:active {
      background-color: ${({ theme }) => theme.colorFillSecondary};
    }
  }
}
`;