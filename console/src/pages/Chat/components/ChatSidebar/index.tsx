import React, { useState, useCallback, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Image } from "antd";
import guideImage from "@/assets/icons/agent_default_logo.png";
import { chatApi } from '@/api/modules/chat';
import type { CronJobSpecOutput } from '@/api/types';
import Style from './style';
import ChatTaskList from '../ChatTaskList';
import { DESIGN_TOKENS } from '@/config/designTokens';
import CollapsedToolbar, { type PanelType } from './CollapsedToolbar';
import ExpandablePanel from './ExpandablePanel';
import {
  buildHistorySessions,
  type HistorySession,
} from './historySessions';

function HistoryIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <circle
        cx="8"
        cy="8"
        r="6"
        stroke={DESIGN_TOKENS.colorTextPrimary}
        strokeWidth="1.5"
      />
      <path
        d="M8 4.5V8L10.5 9.5"
        stroke={DESIGN_TOKENS.colorTextPrimary}
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

function NewTopicIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
      <path d="M6 1V11M1 6H11" stroke="white" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

function SkillMarketIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
      <path
        d="M4.5 3L6 21H18L19.5 3H4.5Z"
        stroke={DESIGN_TOKENS.colorTextSecondary}
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <path
        d="M2 3H22"
        stroke={DESIGN_TOKENS.colorTextSecondary}
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      <path
        d="M9 8L10.5 15"
        stroke={DESIGN_TOKENS.colorTextSecondary}
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      <path
        d="M15 8L13.5 15"
        stroke={DESIGN_TOKENS.colorTextSecondary}
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

function GuideIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
      <rect
        x="4"
        y="3"
        width="16"
        height="18"
        rx="2"
        stroke={DESIGN_TOKENS.colorTextSecondary}
        strokeWidth="1.5"
      />
      <path
        d="M8 8H16M8 12H13"
        stroke={DESIGN_TOKENS.colorTextSecondary}
        strokeWidth="1.5"
        strokeLinecap="round"
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
      className={`chat-sidebar-history-toggle${collapsed ? ' chat-sidebar-history-toggle--collapsed' : ''}`}
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

export interface ChatSidebarProps {
  tasks: CronJobSpecOutput[];
  onCreateSession?: () => void;
  onTaskClick?: (task: CronJobSpecOutput) => void;
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

export default function ChatSidebar(props: ChatSidebarProps) {
  const { tasks, onCreateSession, onTaskClick } = props;
  const navigate = useNavigate();
  const location = useLocation();
  const [historyCollapsed, setHistoryCollapsed] = useState(false);
  const [sessions, setSessions] = useState<HistorySession[]>([]);
  const [collapsed, setCollapsed] = useState(false);
  const [activePanel, setActivePanel] = useState<PanelType>(null);
  const toolbarRef = useRef<HTMLDivElement>(null);
  // Guide image preview state
  const [guidePreviewVisible, setGuidePreviewVisible] = useState(false);

  const currentChatId = location.pathname.match(/^\/chat\/(.+)$/)?.[1] || null;

  const fetchSessions = useCallback(async () => {
    try {
      const chats = await chatApi.listChats();
      setSessions(Array.isArray(chats) ? buildHistorySessions(chats) : []);
    } catch {
      setSessions([]);
    }
  }, []);

  useEffect(() => {
    void fetchSessions();

    const handleFocusRefresh = () => {
      void fetchSessions();
    };
    const handleVisibilityRefresh = () => {
      if (document.visibilityState === 'visible') {
        void fetchSessions();
      }
    };

    window.addEventListener('focus', handleFocusRefresh);
    document.addEventListener('visibilitychange', handleVisibilityRefresh);

    return () => {
      window.removeEventListener('focus', handleFocusRefresh);
      document.removeEventListener('visibilitychange', handleVisibilityRefresh);
    };
  }, [fetchSessions]);

  const handleToggleHistory = useCallback(() => {
    setHistoryCollapsed((prev) => !prev);
  }, []);

  const handleSessionClick = useCallback(
    (sessionId: string) => {
      navigate(`/chat/${sessionId}`, { replace: true });
    },
    [navigate],
  );

  const handleNewTopic = useCallback(() => {
    onCreateSession?.();
  }, [onCreateSession]);

  const handleToggleCollapse = useCallback(() => {
    setCollapsed((prev) => !prev);
    setActivePanel(null);
  }, []);

  const handleNewChat = useCallback(() => {
    setActivePanel(null);
    onCreateSession?.();
  }, [onCreateSession]);

  const handleIconClick = useCallback((panel: PanelType) => {
    setActivePanel(panel);
  }, []);

  const handleClosePanel = useCallback(() => {
    setActivePanel(null);
  }, []);

  const handleTaskOpen = useCallback(
    (task: CronJobSpecOutput) => {
      setActivePanel(null);
      onTaskClick?.(task);
    },
    [onTaskClick],
  );

  const handleOpenGuide = useCallback(() => {
    setGuidePreviewVisible(true);
  }, []);

  if (collapsed) {
    // Calculate total unread execution count for badge
    const unreadCount = tasks.reduce(
      (sum, task) => sum + (task.task?.unread_execution_count || 0),
      0,
    );

    return (
      <>
        <Style />
        <div className="chat-sidebar-wrapper chat-sidebar-wrapper--collapsed">
          <div ref={toolbarRef}>
            <CollapsedToolbar
              activePanel={activePanel}
              onIconClick={handleIconClick}
              onNewChat={handleNewChat}
              taskBadgeCount={unreadCount}
            />
          </div>
          <ExpandablePanel
            visible={activePanel === 'tasks'}
            type="tasks"
            onClose={handleClosePanel}
            tasks={tasks}
            sessions={sessions}
            onTaskClick={handleTaskOpen}
            toolbarRef={toolbarRef}
          />
          <ExpandablePanel
            visible={activePanel === 'history'}
            type="history"
            onClose={handleClosePanel}
            tasks={tasks}
            sessions={sessions}
            onTaskClick={handleTaskOpen}
            toolbarRef={toolbarRef}
          />
          <button
            className="chat-sidebar-collapse-toggle"
            onClick={handleToggleCollapse}
            type="button"
            aria-label="展开侧栏"
          >
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
              <path d="M4 2L7 5L4 8" stroke="rgba(0,0,0,0.35)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>
      </>
    );
  }

  return (
    <>
      <Style />
      <div className="chat-sidebar-wrapper">
        <div className="chat-sidebar">
          <div className="chat-sidebar-content">
            <ChatTaskList tasks={tasks} onTaskClick={handleTaskOpen} />

            <div className="chat-sidebar-history">
              <div
                className="chat-sidebar-history-header"
                onClick={handleToggleHistory}
                role="button"
                tabIndex={0}
              >
                <div className="chat-sidebar-history-title">
                  <HistoryIcon />
                  历史记录({sessions.length})
                </div>
                <ToggleIcon collapsed={historyCollapsed} />
              </div>
              {!historyCollapsed &&
                sessions.map((session) => (
                  <div
                    key={session.id}
                    className="chat-sidebar-history-item"
                    onClick={() => handleSessionClick(session.id!)}
                    role="button"
                    tabIndex={0}
                    style={
                      session.id === currentChatId
                        ? { backgroundColor: 'rgba(55, 105, 252, 0.06)' }
                        : undefined
                    }
                  >
                    <div className="chat-sidebar-history-item-title">
                      {session.name || '新会话'}
                    </div>
                    <div className="chat-sidebar-history-item-time">
                      {formatTime((session as any).createdAt)}
                    </div>
                  </div>
                ))}
            </div>
          </div>

          <div className="chat-sidebar-new-topic">
            <button
              className="chat-sidebar-new-topic-btn"
              onClick={handleNewTopic}
              type="button"
            >
              <NewTopicIcon />
              新建聊天
            </button>
          </div>

          <div className="chat-sidebar-footer">
            {/* 暂时隐藏，后续需要时再开放
            <div className="chat-sidebar-footer-item">
              <SkillMarketIcon />
              skill市场
            </div>
            <div className="chat-sidebar-footer-divider" /> */}
            <div
              className="chat-sidebar-footer-item"
              onClick={handleOpenGuide}
              role="button"
              tabIndex={0}>
              <GuideIcon />
              操作指南
            </div>
          </div>
        </div>
        <button
          className="chat-sidebar-collapse-toggle"
          onClick={handleToggleCollapse}
          type="button"
          aria-label="收起侧栏"
        >
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
            <path d="M6 2L3 5L6 8" stroke="rgba(0,0,0,0.35)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>
      {/* Guide Image Preview */}
      <div style={{ display: "none" }}>
        <Image.PreviewGroup
          preview={{
            visible: guidePreviewVisible,
            onVisibleChange: (vis) => setGuidePreviewVisible(vis),
          }}
        >
          <Image src={guideImage} />
        </Image.PreviewGroup>
      </div>
    </>
  );
}
