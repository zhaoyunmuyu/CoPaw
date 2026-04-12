import React from 'react';
import { Tooltip } from 'antd';
import { NewChatIcon, TasksIcon, HistoryIcon } from './icons';
import Style from './style';
import { DESIGN_TOKENS } from '@/config/designTokens';

export type PanelType = 'tasks' | 'history' | null;

export interface CollapsedToolbarProps {
  activePanel: PanelType;
  onIconClick: (panel: PanelType) => void;
  onNewChat: () => void;
  taskBadgeCount?: number;
}

export default function CollapsedToolbar({
  activePanel,
  onIconClick,
  onNewChat,
  taskBadgeCount = 0,
}: CollapsedToolbarProps) {
  const handleNewChat = () => {
    onNewChat();
  };

  const handleTasks = () => {
    onIconClick(activePanel === 'tasks' ? null : 'tasks');
  };

  const handleHistory = () => {
    onIconClick(activePanel === 'history' ? null : 'history');
  };

  return (
    <>
      <Style />
      <div className="collapsed-toolbar">
        <div className="collapsed-toolbar-icons">
          {/* New Chat */}
          <Tooltip
            title="新建聊天"
            placement="right"
            mouseEnterDelay={0.3}
            overlayStyle={{ pointerEvents: 'none' }}
          >
            <button
              className="collapsed-toolbar-icon-btn"
              onClick={handleNewChat}
              type="button"
              aria-label="新建聊天"
            >
              <NewChatIcon active={false} />
            </button>
          </Tooltip>

          {/* Tasks */}
          <Tooltip
            title="我的任务"
            placement="right"
            mouseEnterDelay={0.3}
            overlayStyle={{ pointerEvents: 'none' }}
          >
            <button
              className="collapsed-toolbar-icon-btn"
              onClick={handleTasks}
              type="button"
              aria-label="我的任务"
            >
              <TasksIcon active={activePanel === 'tasks'} />
              {taskBadgeCount > 0 && (
                <span className="collapsed-toolbar-badge">
                  {taskBadgeCount > 99 ? '99+' : taskBadgeCount}
                </span>
              )}
            </button>
          </Tooltip>

          {/* History */}
          <Tooltip
            title="历史记录"
            placement="right"
            mouseEnterDelay={0.3}
            overlayStyle={{ pointerEvents: 'none' }}
          >
            <button
              className="collapsed-toolbar-icon-btn"
              onClick={handleHistory}
              type="button"
              aria-label="历史记录"
            >
              <HistoryIcon active={activePanel === 'history'} />
            </button>
          </Tooltip>
        </div>
      </div>
    </>
  );
}
