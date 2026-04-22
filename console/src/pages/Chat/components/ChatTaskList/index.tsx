import React, { useState, useCallback } from 'react';
import type { CronJobSpecOutput } from '@/api/types';
import Style from './style';
import { DESIGN_TOKENS } from '@/config/designTokens';
import { getTaskNextRunText, getTaskSidebarMeta } from '../../taskJobs';
import { formatListTime } from '../../listTimeFormat';

function TaskIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path
        d="M2.29 4.3L8 1.05L13.71 4.3V11.7L8 14.95L2.29 11.7V4.3Z"
        stroke={DESIGN_TOKENS.colorTextPrimary}
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ToggleIcon({ collapsed }: { collapsed: boolean }) {
  return (
    <svg
      width="10"
      height="6"
      viewBox="0 0 10 6"
      fill="none"
      className={`chat-task-list-toggle${
        collapsed ? " chat-task-list-toggle--collapsed" : ""
      }`}
    >
      <path
        d="M1 1L5 5L9 1"
        stroke={DESIGN_TOKENS.colorTextMuted}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export interface ChatTaskListProps {
  tasks: CronJobSpecOutput[];
  onTaskClick?: (task: CronJobSpecOutput) => void;
  onTaskResume?: (task: CronJobSpecOutput) => void;
  onTaskDelete?: (task: CronJobSpecOutput) => void;
}

export default function ChatTaskList(props: ChatTaskListProps) {
  const { tasks, onTaskClick, onTaskResume, onTaskDelete } = props;
  const [collapsed, setCollapsed] = useState(false);

  const handleToggle = useCallback(() => {
    setCollapsed((prev) => !prev);
  }, []);

  const handleTaskClick = useCallback(
    (task: CronJobSpecOutput) => {
      onTaskClick?.(task);
    },
    [onTaskClick],
  );

  const handleTaskResume = useCallback(
    (event: React.MouseEvent<HTMLButtonElement>, task: CronJobSpecOutput) => {
      event.stopPropagation();
      onTaskResume?.(task);
    },
    [onTaskResume],
  );

  const handleTaskDelete = useCallback(
    (event: React.MouseEvent<HTMLButtonElement>, task: CronJobSpecOutput) => {
      event.stopPropagation();
      onTaskDelete?.(task);
    },
    [onTaskDelete],
  );

  return (
    <>
      <Style />
      <div className="chat-task-list">
        <div
          className="chat-task-list-header"
          onClick={handleToggle}
          role="button"
          tabIndex={0}
        >
          <div className="chat-task-list-title">
            <TaskIcon />
            我的任务({tasks.length})
          </div>
          <ToggleIcon collapsed={collapsed} />
        </div>
        {!collapsed && (
          <div className="chat-task-list-items">
            {tasks.length === 0 ? (
              <div className="chat-task-list-empty">暂无任务</div>
            ) : (
              tasks.map((task) => {
                const sidebarMeta = getTaskSidebarMeta(task);
                const nextRunText = getTaskNextRunText(task);

                return (
                  <div
                    key={task.id}
                    className={`chat-task-list-item${
                      sidebarMeta.state !== 'active' &&
                      sidebarMeta.state !== 'running'
                        ? ' chat-task-list-item--paused'
                        : ''
                    }${
                      sidebarMeta.state === 'running'
                        ? ' chat-task-list-item--running'
                        : ''
                    }${
                      sidebarMeta.state === 'auto-paused'
                        ? ' chat-task-list-item--auto-paused'
                        : ''
                    }`}
                    onClick={() => handleTaskClick(task)}
                    role="button"
                    tabIndex={0}
                  >
                    <div className="chat-task-list-item-header">
                      <span className="chat-task-list-item-title">
                        {task.name || task.id}
                      </span>
                      {sidebarMeta.canResume ? (
                        <div className="chat-task-list-item-actions">
                          <button
                            type="button"
                            className="chat-task-list-item-action chat-task-list-item-action--delete"
                            onClick={(event) => handleTaskDelete(event, task)}
                          >
                            删除
                          </button>
                          <button
                            type="button"
                            className="chat-task-list-item-action"
                            onClick={(event) => handleTaskResume(event, task)}
                          >
                            恢复
                          </button>
                        </div>
                      ) : (
                        sidebarMeta.unreadCount > 0 && (
                          <span className="chat-task-list-item-badge">
                            {sidebarMeta.unreadCount > 99
                              ? '99+'
                              : sidebarMeta.unreadCount}
                          </span>
                        )
                      )}
                    </div>
                    {sidebarMeta.state !== 'active' &&
                      sidebarMeta.state !== 'running' && (
                      <div
                        className={`chat-task-list-item-status ${
                          sidebarMeta.state === 'auto-paused'
                            ? 'chat-task-list-item-status--auto'
                            : 'chat-task-list-item-status--manual'
                        }`}
                      >
                        {sidebarMeta.state === 'auto-paused'
                          ? `已自动暂停 · 连续 ${sidebarMeta.unreadCount} 次未读`
                          : '已手动暂停'}
                      </div>
                    )}
                    {(task.task?.latest_scheduled_preview ||
                      task.task?.last_scheduled_run_at) && (
                      <div className="chat-task-list-item-subtitle">
                        {task.task?.last_scheduled_run_at && (
                          <span className="chat-task-list-item-time">
                            {formatListTime(task.task.last_scheduled_run_at)}
                          </span>
                        )}
                        {task.task?.latest_scheduled_preview}
                      </div>
                    )}
                    {nextRunText && (
                      <div className="chat-task-list-item-next-run">
                        {nextRunText}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        )}
      </div>
    </>
  );
}
