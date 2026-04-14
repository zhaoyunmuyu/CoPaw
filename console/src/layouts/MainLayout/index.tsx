import { Layout } from "antd";
import {
  Routes,
  Route,
  useLocation,
  Navigate,
} from "react-router-dom";

// ==================== iframe 集成 (Kun He) ====================
// useSearchParams: 获取 URL 参数，用于判断 origin 参数是否为 "Y"
// useIframeStore: 获取父窗口传递的 hideMenu 参数
import { useSearchParams } from "react-router-dom";
import { useIframeStore } from "../../stores/iframeStore";
// ==================== iframe 集成结束 ====================

import Sidebar from "../Sidebar";
import Header from "../Header";
import ConsoleCronBubble from "../../components/ConsoleCronBubble";
import styles from "../index.module.less";
import Chat from "../../pages/Chat";
import ChannelsPage from "../../pages/Control/Channels";
import SessionsPage from "../../pages/Control/Sessions";
import CronJobsPage from "../../pages/Control/CronJobs";
import HeartbeatPage from "../../pages/Control/Heartbeat";
import AgentConfigPage from "../../pages/Agent/Config";
import SkillsPage from "../../pages/Agent/Skills";
import SkillPoolPage from "../../pages/Agent/SkillPool";
import ToolsPage from "../../pages/Agent/Tools";
import WorkspacePage from "../../pages/Agent/Workspace";
import MCPPage from "../../pages/Agent/MCP";
import ModelsPage from "../../pages/Settings/Models";
import EnvironmentsPage from "../../pages/Settings/Environments";
import SecurityPage from "../../pages/Settings/Security";
import TokenUsagePage from "../../pages/Settings/TokenUsage";
import VoiceTranscriptionPage from "../../pages/Settings/VoiceTranscription";
import AgentsPage from "../../pages/Settings/Agents";
import AnalyticsPage from "../../pages/Analytics";
import InstancePage from "../../pages/Instance";

const { Content } = Layout;

const pathToKey: Record<string, string> = {
  "/chat": "chat",
  "/channels": "channels",
  "/sessions": "sessions",
  "/cron-jobs": "cron-jobs",
  "/heartbeat": "heartbeat",
  "/skills": "skills",
  "/skill-pool": "skill-pool",
  "/tools": "tools",
  "/mcp": "mcp",
  "/workspace": "workspace",
  "/agents": "agents",
  "/models": "models",
  "/environments": "environments",
  "/agent-config": "agent-config",
  "/security": "security",
  "/token-usage": "token-usage",
  "/voice-transcription": "voice-transcription",
  "/analytics/overview": "analytics-overview",
  "/analytics/users": "analytics-users",
  "/analytics/sessions": "analytics-sessions",
  "/analytics/messages": "analytics-messages",
  "/analytics/traces": "analytics-traces",
  "/instance/overview": "instance-overview",
  "/instance/instances": "instance-instances",
  "/instance/allocations": "instance-allocations",
  "/instance/operation-logs": "instance-operation-logs",
};

export default function MainLayout() {
  const location = useLocation();
  const currentPath = location.pathname;
  const selectedKey = pathToKey[currentPath] || "chat";

  // ==================== iframe 集成 (Kun He) ====================
  // Sidebar 显示控制逻辑：
  // 1. URL 参数 origin === "Y" 时隐藏 Sidebar
  // 2. iframe 传递的 hideMenu === true 时隐藏 Sidebar
  // 用途：支持父应用控制子应用的菜单显示
  const [searchParams] = useSearchParams();
  const hideMenu = useIframeStore((state) => state.hideMenu);
  const originParam = searchParams.get("origin");
  const shouldHideSidebar = originParam === "Y" || hideMenu;
  // ==================== iframe 集成结束 ====================

  return (
    <Layout className={styles.mainLayout}>
      {/* ==================== 首页改版 (Kun He) ==================== */}
      {/* Header 和 Sidebar 一起根据 hideMenu 控制显隐 */}
      {!shouldHideSidebar && <Header />}
      {/* ==================== 首页改版结束 ==================== */}
      <Layout>
        {/* ==================== iframe 集成 (Kun He) ==================== */}
        {/* 条件渲染 Sidebar：根据 origin 参数或 hideMenu 决定是否显示 */}
        {!shouldHideSidebar && <Sidebar selectedKey={selectedKey} />}
        {/* ==================== iframe 集成结束 ==================== */}
        <Content className="page-container">
          <ConsoleCronBubble />
          <div className="page-content">
            <Routes>
              <Route path="/" element={<Navigate to="/chat" replace />} />
              <Route path="/chat/*" element={<Chat />} />
              <Route path="/channels" element={<ChannelsPage />} />
              <Route path="/sessions" element={<SessionsPage />} />
              <Route path="/cron-jobs" element={<CronJobsPage />} />
              <Route path="/heartbeat" element={<HeartbeatPage />} />
              <Route path="/skills" element={<SkillsPage />} />
              <Route path="/skill-pool" element={<SkillPoolPage />} />
              <Route path="/tools" element={<ToolsPage />} />
              <Route path="/mcp" element={<MCPPage />} />
              <Route path="/workspace" element={<WorkspacePage />} />
              <Route path="/agents" element={<AgentsPage />} />
              <Route path="/models" element={<ModelsPage />} />
              <Route path="/environments" element={<EnvironmentsPage />} />
              <Route path="/agent-config" element={<AgentConfigPage />} />
              <Route path="/security" element={<SecurityPage />} />
              <Route path="/token-usage" element={<TokenUsagePage />} />
              <Route
                path="/voice-transcription"
                element={<VoiceTranscriptionPage />}
              />
              <Route path="/analytics/*" element={<AnalyticsPage />} />
              <Route path="/instance/*" element={<InstancePage />} />
            </Routes>
          </div>
        </Content>
      </Layout>
    </Layout>
  );
}
