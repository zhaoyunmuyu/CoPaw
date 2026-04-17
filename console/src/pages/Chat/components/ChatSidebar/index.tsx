import { useState, useCallback, useRef, useMemo, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Image } from "antd";
import guideImage from "@/assets/icons/agent_default_logo.png";
import type { CronJobSpecOutput } from '@/api/types';
import Style from './style';
import ChatTaskList from '../ChatTaskList';
import { DESIGN_TOKENS } from '@/config/designTokens';
import CollapsedToolbar, { type PanelType } from './CollapsedToolbar';
import ExpandablePanel from './ExpandablePanel';
import type { HistorySession } from './historySessions';
import { useChatAnywhereSessionsState } from '@/components/agentscope-chat';
import { formatListTime } from '../../listTimeFormat';
import sessionApi from '../../sessionApi';

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
  onTaskResume?: (task: CronJobSpecOutput) => void;
  onTaskDelete?: (task: CronJobSpecOutput) => void;
}

export default function ChatSidebar(props: ChatSidebarProps) {
  const { tasks, onCreateSession, onTaskClick, onTaskResume, onTaskDelete } =
    props;
  const navigate = useNavigate();
  const location = useLocation();
  const [historyCollapsed, setHistoryCollapsed] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [activePanel, setActivePanel] = useState<PanelType>(null);
  const toolbarRef = useRef<HTMLDivElement>(null);
  // Guide image preview state
  const [guidePreviewVisible, setGuidePreviewVisible] = useState(false);
  const { sessions: sharedSessions, setSessionLoading, setSessions } = useChatAnywhereSessionsState();

  const currentChatId = location.pathname.match(/^\/chat\/(.+)$/)?.[1] || null;

  // 刷新共享 sessions 状态
  const refreshSessions = useCallback(async () => {
    try {
      const sessionList = await sessionApi.getSessionList();
      setSessions(sessionList);
    } catch {
      // ignore
    }
  }, [setSessions]);

  // 监听 focus/visibilitychange 刷新 sessions
  useEffect(() => {
    const handleFocusRefresh = () => {
      void refreshSessions();
    };
    const handleVisibilityRefresh = () => {
      if (document.visibilityState === 'visible') {
        void refreshSessions();
      }
    };

    window.addEventListener('focus', handleFocusRefresh);
    document.addEventListener('visibilitychange', handleVisibilityRefresh);

    return () => {
      window.removeEventListener('focus', handleFocusRefresh);
      document.removeEventListener('visibilitychange', handleVisibilityRefresh);
    };
  }, [refreshSessions]);

  // 使用共享 sessions 状态，过滤并转换
  const sessions = useMemo(() => {
    return sharedSessions
      .filter((s) => (s as HistorySession).meta?.session_kind !== "task")
      .map((s) => {
        const hs = s as HistorySession;
        return {
          ...hs,
          createdAt: hs.createdAt || new Date(parseInt(s.id)).toISOString(),
        };
      });
  }, [sharedSessions]);

  const handleToggleHistory = useCallback(() => {
    setHistoryCollapsed((prev) => !prev);
  }, []);

  const handleSessionClick = useCallback(
    (sessionId: string) => {
      // 先设置 loading 状态，避免导航后闪现欢迎页
      setSessionLoading(true);
      navigate(`/chat/${sessionId}`, { replace: true });
    },
    [navigate, setSessionLoading],
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
              onTaskResume={onTaskResume}
              onTaskDelete={onTaskDelete}
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
            <ChatTaskList
              tasks={tasks}
              onTaskClick={handleTaskOpen}
              onTaskResume={onTaskResume}
              onTaskDelete={onTaskDelete}
            />

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
                      {formatListTime((session as any).createdAt)}
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
