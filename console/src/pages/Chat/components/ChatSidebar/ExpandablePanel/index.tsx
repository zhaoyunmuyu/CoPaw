import React, { useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { cronJobApi } from '@/api/modules/cronjob';
import type { CronJobSpecOutput } from '@/api/types';
import type { IAgentScopeRuntimeWebUISession } from '@/components/agentscope-chat';
import sessionApi from '../../../sessionApi';
import { TasksIconSmall, HistoryIconSmall } from '../CollapsedToolbar/icons';
import { DESIGN_TOKENS } from '@/config/designTokens';
import Style from './style';

export interface ExpandablePanelProps {
  visible: boolean;
  type: 'tasks' | 'history';
  onClose: () => void;
  /** For click-outside detection — the toolbar element ref */
  toolbarRef: React.RefObject<HTMLElement | null>;
}

/** Format ISO timestamp to YYYY-MM-DD HH:mm */
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
  toolbarRef,
}: ExpandablePanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  // Click-outside detection
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

    // Use mousedown for immediate response, delay to avoid same-click closing
    const timer = setTimeout(() => {
      document.addEventListener('mousedown', handleClickOutside);
    }, 0);

    return () => {
      clearTimeout(timer);
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [visible, onClose, toolbarRef]);

  // Escape key to close
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
        {type === 'tasks' ? <TasksContent /> : <HistoryContent onClose={onClose} />}
      </div>
    </>
  );
}

// ─── Tasks Panel Content ───

function TasksContent() {
  const [tasks, setTasks] = React.useState<CronJobSpecOutput[]>([]);

  useEffect(() => {
    cronJobApi
      .listCronJobs()
      .then((data) => setTasks(Array.isArray(data) ? data : []))
      .catch(() => setTasks([]));
  }, []);

  const handleTaskClick = useCallback((task: CronJobSpecOutput) => {
    cronJobApi.triggerCronJob(task.id).catch(() => {});
  }, []);

  return (
    <>
      <div className="expandable-panel-header">
        <TasksIconSmall />
        <span className="expandable-panel-header-title">
          我的任务({tasks.length})
        </span>
      </div>
      <div className="expandable-panel-content">
        {tasks.length === 0 ? (
          <div className="expandable-panel-empty">暂无任务</div>
        ) : (
          tasks.map((task) => (
            <div
              key={task.id}
              className="expandable-panel-task-card"
              onClick={() => handleTaskClick(task)}
              role="button"
              tabIndex={0}
            >
              <div className="expandable-panel-task-title-row">
                <span className="expandable-panel-task-title">
                  {task.name || task.text || task.id}
                </span>
                {/* Badge placeholder — will be driven by unread count when API supports it */}
              </div>
              {task.text && task.name && (
                <div className="expandable-panel-task-subtitle">
                  {task.text}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </>
  );
}

// ─── History Panel Content ───

function HistoryContent({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate();
  const [sessions, setSessions] = React.useState<IAgentScopeRuntimeWebUISession[]>([]);

  useEffect(() => {
    sessionApi
      .getSessionList()
      .then((list) => setSessions(Array.isArray(list) ? list : []))
      .catch(() => setSessions([]));
  }, []);

  const handleSessionClick = useCallback(
    (sessionId: string) => {
      const realId = sessionApi.getRealIdForSession(sessionId) || sessionId;
      navigate(`/chat/${realId}`, { replace: true });
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
