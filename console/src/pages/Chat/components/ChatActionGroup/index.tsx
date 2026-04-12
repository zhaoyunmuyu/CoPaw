import React from "react";
import { IconButton } from "@agentscope-ai/design";
import { SparkNewChatFill } from "@agentscope-ai/icons";
// ==================== 组件引入方式变更 (Kun He) ====================
import { useChatAnywhereSessions } from '@/components/agentscope-chat';
// ==================== 组件引入方式变更结束 ====================
import { useTranslation } from "react-i18next";
import { Flex, Tooltip } from "antd";
// ==================== 首页改版 (Kun He) ====================
// 历史记录已迁移到左侧 ChatSidebar，不再需要右侧 Drawer 和历史按钮
// import ChatSessionDrawer from "../ChatSessionDrawer";
// ==================== 首页改版结束 ====================

const ChatActionGroup: React.FC = () => {
  const { t } = useTranslation();
  const { createSession } = useChatAnywhereSessions();

  return (
    <Flex gap={8} align="center">
      <Tooltip title={t("chat.newChatTooltip")} mouseEnterDelay={0.5}>
        <IconButton
          bordered={false}
          icon={<SparkNewChatFill />}
          onClick={() => createSession()}
        />
      </Tooltip>
      {/* ==================== 首页改版 (Kun He) ==================== */}
      {/* 历史按钮已移除，历史记录在左侧 ChatSidebar 中展示 */}
      {/* ==================== 首页改版结束 ==================== */}
    </Flex>
  );
};

export default ChatActionGroup;
