import React, { useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import type { CronJobSpecOutput } from '@/api/types';
import type { IAgentScopeRuntimeWebUISession } from '@/components/agentscope-chat';
import { TasksIconSmall, HistoryIconSmall } from '../CollapsedToolbar/icons';
import Style from './style';

export interface ExpandablePanelProps {
  visible: boolean;
  type: 'tasks' | 'history';
  onClose: () => void;
  tasks: CronJobSpecOutput[];
  sessions: IAgentScopeRuntimeWebUISession[];
  onTaskClick: (task: CronJobSpecOutput) => void;
  toolbarRef: React.RefObject<HTMLElement | null>;
}

function formatTime(raw: string | null | undefined): string {
  if (!raw) return '';
  const date = new Date(raw);
  if (isNaN(date.getTime())) return '';
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(
    date.getDate(),
  )} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export default function ExpandablePanel({
  visible,
  type,
  onClose,
  tasks,
  sessions,
  onTaskClick,
  toolbarRef,
}: ExpandablePanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!visible) return;

    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (
        panelRef.current &&
        !panelRef.current.contains(target) &&
        toolbarRef.current &&
        !toolbarRef.current.contains(target)
      ) {
        onClose();
      }
    };

    const timer = setTimeout(() => {
      document.addEventListener('mousedown', handleClickOutside);
    }, 0);

    return () => {
      clearTimeout(timer);
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [visible, onClose, toolbarRef]);

  useEffect(() => {
    if (!visible) return;
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [visible, onClose]);

  if (!visible) return null;

  return (
    <>
      <Style />
      <div className="expandable-panel" ref={panelRef}>
        {type === 'tasks' ? (
          <TasksContent tasks={tasks} onTaskClick={onTaskClick} />
        ) : (
          <HistoryContent sessions={sessions} onClose={onClose} />
        )}
      </div>
    </>
  );
}

function TasksContent({
  tasks,
  onTaskClick,
}: {
  tasks: CronJobSpecOutput[];
  onTaskClick: (task: CronJobSpecOutput) => void;
}) {
  return (
    <>
      <div className="expandable-panel-header">
        <TasksIconSmall />
        <span className="expandable-panel-header-title">我的任务({tasks.length})</span>
      </div>
      <div className="expandable-panel-content">
        {tasks.length === 0 ? (
          <div className="expandable-panel-empty">暂无任务</div>
        ) : (
          tasks.map((task) => (
            <div
              key={task.id}
              className="expandable-panel-task-card"
              onClick={() => onTaskClick(task)}
              role="button"
              tabIndex={0}
            >
              <div className="expandable-panel-task-title-row">
                <span className="expandable-panel-task-title">
                  {task.name || task.id}
                </span>
                {(task.task?.unread_execution_count || 0) > 0 && (
                  <span className="expandable-panel-task-badge">
                    {task.task!.unread_execution_count > 99
                      ? '99+'
                      : task.task!.unread_execution_count}
                  </span>
                )}
              </div>
              {(task.task?.latest_scheduled_preview || task.task?.last_scheduled_run_at) && (
                <div className="expandable-panel-task-subtitle">
                  {task.task?.last_scheduled_run_at && (
                    <span className="expandable-panel-task-time">
                      {formatTime(task.task.last_scheduled_run_at)}
                    </span>
                  )}
                  {task.task?.latest_scheduled_preview}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </>
  );
}

function HistoryContent({
  sessions,
  onClose,
}: {
  sessions: IAgentScopeRuntimeWebUISession[];
  onClose: () => void;
}) {
  const navigate = useNavigate();

  const handleSessionClick = useCallback(
    (sessionId: string) => {
      navigate(`/chat/${sessionId}`, { replace: true });
      onClose();
    },
    [navigate, onClose],
  );

  return (
    <>
      <div className="expandable-panel-header">
        <HistoryIconSmall />
        <span className="expandable-panel-header-title">
          历史记录({sessions.length})
        </span>
      </div>
      <div className="expandable-panel-content">
        {sessions.length === 0 ? (
          <div className="expandable-panel-empty">暂无历史记录</div>
        ) : (
          sessions.map((session) => (
            <div
              key={session.id}
              className="expandable-panel-history-item"
              onClick={() => handleSessionClick(session.id!)}
              role="button"
              tabIndex={0}
            >
              <div className="expandable-panel-history-title">
                {session.name || '新会话'}
              </div>
              <div className="expandable-panel-history-time">
                {formatTime((session as any).createdAt)}
              </div>
            </div>
          ))
        )}
      </div>
    </>
  );
}
