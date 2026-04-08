import React from "react";
// ==================== 组件引入方式变更 (Kun He) ====================
import { useChatAnywhereSessionsState } from '@/components/agentscope-chat';
// ==================== 组件引入方式变更结束 ====================
import styles from "./index.module.less";

const ChatHeaderTitle: React.FC = () => {
  const { sessions, currentSessionId } = useChatAnywhereSessionsState();
  const currentSession = sessions.find((s) => s.id === currentSessionId);
  const chatName = currentSession?.name || "新会话";

  return <span className={styles.chatName}>{chatName}</span>;
};

export default ChatHeaderTitle;
