import { createGlobalStyle } from 'antd-style';

export default createGlobalStyle`
.drag-upload-overlay {
  position: absolute;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.08);
}

.drag-upload-card {
  width: 800px;
  height: 329px;
  background: #F1F6FF;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  position: relative;
  gap: 0;
}

.drag-upload-close {
  position: absolute;
  top: 12px;
  right: 12px;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  background: none;
  border: none;
  border-radius: 4px;
  transition: background 0.15s ease;

  &:hover {
    background: rgba(0, 0, 0, 0.06);
  }
}

.drag-upload-icon {
  width: 66px;
  height: 66px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 20px;
}

.drag-upload-title {
  font-size: 20px;
  font-weight: 500;
  color: #11142D;
  line-height: 27px;
  text-align: center;
}

.drag-upload-desc {
  font-size: 14px;
  color: #808191;
  line-height: 19px;
  margin-top: 8px;
  text-align: center;
}
`;
