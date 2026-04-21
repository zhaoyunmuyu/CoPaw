import { useState, useCallback, useRef, useMemo, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Image } from "antd";
import { useContextSelector } from "use-context-selector";
import Style from './style';
import ChatTaskList from '../ChatTaskList';
import type { CronJobSpecOutput } from '@/api/types';
import { DESIGN_TOKENS } from '@/config/designTokens';
import CollapsedToolbar, { type PanelType } from './CollapsedToolbar';
import ExpandablePanel from './ExpandablePanel';
import type { HistorySession } from './historySessions';
import sendIcon from '../../../../assets/icons/new_chat.svg'
import operateIcon from '../../../../assets/icons/operate.svg'
import guideImage from '@/assets/others/note.png'
// import { useChatAnywhereSessionsState } from '@/components/agentscope-chat';
import { ChatAnywhereSessionsContext } from '@/components/agentscope-chat';
import { formatListTime } from '../../listTimeFormat';
import sessionApi from '../../sessionApi';
import { HistorySessionRow } from './HistorySessionRow';
import ChatSessionItem from '../ChatSessionItem';
import { chatApi } from '@/api/modules/chat';


/** Extended session type with additional backend fields */
interface ExtendedHistorySession extends HistorySession {
  channel?: string;
  realId?: string;
}


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
  // const { sessions: sharedSessions, setSessionLoading, setSessions } = useChatAnywhereSessionsState();
  const sharedSessions = useContextSelector(
    ChatAnywhereSessionsContext,
    (value) => value.sessions,
  );
  const setSessionLoading = useContextSelector(
    ChatAnywhereSessionsContext,
    (value) => value.setSessionLoading,
  );
  const setSessions = useContextSelector(
    ChatAnywhereSessionsContext,
    (value) => value.setSessions,
  );


  const currentChatId = location.pathname.match(/^\/chat\/(.+)$/)?.[1] || null;
  const currentChatIdRef = useRef<string | null>(currentChatId);
  currentChatIdRef.current = currentChatId;


  // 刷新共享 sessions 状态
  const refreshSessions = useCallback(async () => {
    try {
      const sessionList = await sessionApi.getSessionList();
      setSessions(sessionList);
    } catch {
      // ignore
    }
  }, [setSessions]);


  // 监听 visibilitychange 刷新 sessions
  useEffect(() => {
    const handleVisibilityRefresh = () => {
      if (document.visibilityState === 'visible') {
        void refreshSessions();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityRefresh);

    return () => {
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
  const sessionsRef = useRef(sessions);
  sessionsRef.current = sessions;


  const handleToggleHistory = useCallback(() => {
    setHistoryCollapsed((prev) => !prev);
  }, []);

  const handleSessionClick = useCallback(
    (sessionId: string) => {
      // Skip if already on the same session
      if (currentChatIdRef.current === sessionId) return;

      // Set loading first to avoid showing welcome page briefly
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

  const handleDeleteSession = useCallback(
    async (sessionId: string, backendId: string | null) => {
      // const session = sessions.find((s) => s.id === sessionId) as ExtendedHistorySession | undefined;
      // const backendId = session?.realId || (/^\d+$/.test(sessionId) ? null : sessionId);

      if (backendId) {
        await chatApi.deleteChat(backendId);
      }

      if (currentChatIdRef.current === sessionId) {
        const next = sessionsRef.current.filter((s) => s.id !== sessionId);
        if (next[0]?.id) {
          navigate(`/chat/${next[0].id}`, { replace: true });
        } else {
          navigate('/chat', { replace: true });
        }
      }

      await refreshSessions();
    },
    [refreshSessions, navigate],
    // [sessions, currentChatId, refreshSessions, navigate],
  );

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
            <div className="chat-sidebar-new-topic">
              <button
                className="chat-sidebar-new-topic-btn"
                onClick={handleNewTopic}
                type="button"
              >
                <img src={sendIcon} alt="+" width="16" height="16" />
                新建会话
              </button>
            </div>
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
                sessions.map((session) => {
                  const ext = session as ExtendedHistorySession;
                  return (
                    <HistorySessionRow
                      key={session.id}
                      name={session.name || '新会话'}
                      session={ext}
                      active={session.id === currentChatId}
                      onSessionClick={handleSessionClick}
                      onSessionDelete={handleDeleteSession}
                    />
                    // <ChatSessionItem
                    //   key={session.id}
                    //   name={session.name || '新会话'}
                    //   time={formatListTime(ext.createdAt)}
                    //   active={session.id === currentChatId}
                    //   onClick={() => handleSessionClick(session.id!)}
                    //   onDelete={() => handleDeleteSession(session.id!)}
                    //   showEdit={false}
                    //   showTimeline={false}
                    //   showChannel={false}
                    // />
                  );
                })}
            </div>
          </div>


          <div className="chat-sidebar-footer">
            {/* 暂时隐藏，后续需要时再开放
            <div className="chat-sidebar-footer-item">
              <img src={skillMarketIcon} alt="发送" width="24" height="24" />
              skill市场
            </div>
            <div className="chat-sidebar-footer-divider" /> */}
            <div
              className="chat-sidebar-footer-item"
              onClick={handleOpenGuide}
              role="button"
              tabIndex={0}>
              <img src={operateIcon} alt="note" width="20" height="20" />
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