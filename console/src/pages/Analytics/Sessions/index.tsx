import { useEffect, useState, useRef } from "react";
import { useTranslation } from "react-i18next";
import {
  Table,
  Card,
  Input,
  DatePicker,
  Spin,
  Tag,
  Descriptions,
  Timeline,
  Empty,
  Drawer,
} from "antd";
import {
  Search,
  MessageSquare,
  Clock,
  FileText,
  Cpu,
  Zap,
  Plug,
  User,
} from "lucide-react";
import type { ColumnsType } from "antd/es/table";
import dayjs from "dayjs";
import {
  tracingApi,
  SessionListItem,
  SessionStats,
  TraceListItem,
  TraceDetail,
} from "../../../api/modules/tracing";
import styles from "./index.module.less";

const { RangePicker } = DatePicker;

export default function SessionsPage() {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [sessions, setSessions] = useState<SessionListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [searchQuery, setSearchQuery] = useState("");
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(
    null,
  );

  // 详情抽屉状态
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedSession, setSelectedSession] =
    useState<SessionListItem | null>(null);
  const [sessionStats, setSessionStats] = useState<SessionStats | null>(null);
  const [sessionLoading, setSessionLoading] = useState(false);

  // 对话列表状态
  const [traces, setTraces] = useState<TraceListItem[]>([]);
  const [tracesTotal, setTracesTotal] = useState(0);
  const [tracesLoading, setTracesLoading] = useState(false);

  // 对话详情状态
  const [selectedTrace, setSelectedTrace] = useState<TraceListItem | null>(
    null,
  );
  const [traceDetail, setTraceDetail] = useState<TraceDetail | null>(null);
  const [traceLoading, setTraceLoading] = useState(false);

  // 用于追踪筛选条件变化，避免 useEffect 重复触发
  const filtersRef = useRef({
    searchQuery: "",
    dateRange: null as [dayjs.Dayjs, dayjs.Dayjs] | null,
  });

  useEffect(() => {
    // 检查筛选条件是否变化
    const filtersChanged =
      filtersRef.current.searchQuery !== searchQuery ||
      filtersRef.current.dateRange !== dateRange;

    // 更新 ref
    filtersRef.current = { searchQuery, dateRange };

    // 如果筛选条件变化且不是第一页，只重置页码不查询
    if (filtersChanged && page !== 1) {
      setPage(1);
      return;
    }

    fetchSessions();
  }, [page, pageSize, searchQuery, dateRange]);

  const fetchSessions = async () => {
    setLoading(true);
    try {
      const data = await tracingApi.getSessions(page, pageSize, {
        user_id: searchQuery || undefined,
        start_date: dateRange?.[0]?.format("YYYY-MM-DD"),
        end_date: dateRange?.[1]?.format("YYYY-MM-DD"),
      });
      setSessions(data.items || []);
      setTotal(data.total || 0);
    } catch (error) {
      console.error("Failed to fetch sessions:", error);
    } finally {
      setLoading(false);
    }
  };

  const fetchSessionDetail = async (session: SessionListItem) => {
    setSelectedSession(session);
    setDrawerOpen(true);
    setSessionLoading(true);
    setTraces([]);
    setSelectedTrace(null);
    setTraceDetail(null);

    try {
      // 获取会话统计
      const stats = await tracingApi.getSessionStats(session.session_id);
      setSessionStats(stats);

      // 获取会话下的对话列表
      setTracesLoading(true);
      const tracesData = await tracingApi.getTraces(1, 20, {
        session_id: session.session_id,
      });
      setTraces(tracesData.items || []);
      setTracesTotal(tracesData.total || 0);
    } catch (error) {
      console.error("Failed to fetch session detail:", error);
    } finally {
      setSessionLoading(false);
      setTracesLoading(false);
    }
  };

  const fetchTraceDetail = async (trace: TraceListItem) => {
    setSelectedTrace(trace);
    setTraceLoading(true);
    try {
      const detail = await tracingApi.getTraceDetail(trace.trace_id);
      setTraceDetail(detail);
    } catch (error) {
      console.error("Failed to fetch trace detail:", error);
    } finally {
      setTraceLoading(false);
    }
  };

  const handleDrawerClose = () => {
    setDrawerOpen(false);
    setSelectedSession(null);
    setSessionStats(null);
    setTraces([]);
    setSelectedTrace(null);
    setTraceDetail(null);
  };

  const formatTokens = (tokens: number) => {
    if (!tokens) return "0";
    if (tokens < 1000) return tokens.toString();
    if (tokens < 1000000) return `${(tokens / 1000).toFixed(1)}K`;
    return `${(tokens / 1000000).toFixed(2)}M`;
  };

  const formatDuration = (ms: number | null) => {
    if (ms === null || ms === undefined) return "-";
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${(ms / 60000).toFixed(1)}m`;
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "completed":
        return "success";
      case "running":
        return "processing";
      case "error":
        return "error";
      case "cancelled":
        return "default";
      default:
        return "default";
    }
  };

  const columns: ColumnsType<SessionListItem> = [
    {
      title: t("analytics.sessionId", "Session ID"),
      dataIndex: "session_id",
      key: "session_id",
      width: 160,
      ellipsis: true,
      render: (v) => (
        <span style={{ cursor: "pointer", color: "#1890ff" }}>{v}</span>
      ),
    },
    {
      title: t("analytics.userId", "User ID"),
      dataIndex: "user_id",
      key: "user_id",
      width: 120,
      ellipsis: true,
    },
    {
      title: t("analytics.channel", "Channel"),
      dataIndex: "channel",
      key: "channel",
      width: 80,
    },
    {
      title: t("analytics.traces", "Traces"),
      dataIndex: "total_traces",
      key: "total_traces",
      width: 80,
    },
    {
      title: t("analytics.tokens", "Tokens"),
      dataIndex: "total_tokens",
      key: "total_tokens",
      width: 80,
      render: (v) => formatTokens(v),
    },
    {
      title: t("analytics.skills", "Skills"),
      dataIndex: "total_skills",
      key: "total_skills",
      width: 80,
    },
    {
      title: t("analytics.lastActive", "Last Active"),
      dataIndex: "last_active",
      key: "last_active",
      width: 120,
      render: (v) => (v ? dayjs(v).format("MM-DD HH:mm") : "-"),
    },
  ];

  return (
    <div className={styles.sessionsPage}>
      <div className={styles.header}>
        <h2>{t("analytics.sessionAnalysis", "Session Analysis")}</h2>
        <div className={styles.filters}>
          <RangePicker
            value={dateRange}
            onChange={(dates) =>
              setDateRange(dates as [dayjs.Dayjs, dayjs.Dayjs] | null)
            }
            allowClear
          />
          <Input
            placeholder={t("analytics.searchUser", "Search user...")}
            prefix={<Search size={16} />}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ width: 250 }}
            allowClear
          />
        </div>
      </div>

      <Card>
        <Table
          dataSource={sessions}
          columns={columns}
          rowKey="session_id"
          loading={loading}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total) => t("analytics.totalItems", { total }),
            onChange: (p, ps) => {
              setPage(p);
              setPageSize(ps);
            },
          }}
          onRow={(record) => ({
            onClick: () => fetchSessionDetail(record),
            style: { cursor: "pointer" },
          })}
        />
      </Card>

      <Drawer
        title={
          <span>
            <MessageSquare size={18} style={{ marginRight: 8 }} />
            {selectedSession?.session_id ||
              t("analytics.sessionDetails", "Session Details")}
          </span>
        }
        placement="right"
        width={600}
        open={drawerOpen}
        onClose={handleDrawerClose}
      >
        {sessionLoading ? (
          <div className={styles.drawerLoading}>
            <Spin />
          </div>
        ) : sessionStats ? (
          <div className={styles.drawerContent}>
            {/* 统计卡片 */}
            <div className={styles.statsRow}>
              <div className={styles.statItem}>
                <div className={styles.value}>{sessionStats.total_traces}</div>
                <div className={styles.label}>
                  {t("analytics.traces", "Traces")}
                </div>
              </div>
              <div className={styles.statItem}>
                <div className={styles.value}>
                  {formatTokens(sessionStats.total_tokens)}
                </div>
                <div className={styles.label}>
                  {t("analytics.tokens", "Tokens")}
                </div>
              </div>
              <div className={styles.statItem}>
                <div className={styles.value}>
                  {formatDuration(sessionStats.avg_duration_ms)}
                </div>
                <div className={styles.label}>
                  {t("analytics.avgDuration", "Avg Duration")}
                </div>
              </div>
            </div>

            {/* 基本信息 */}
            <Descriptions column={2} size="small" bordered>
              <Descriptions.Item
                label={t("analytics.userId", "User ID")}
                span={2}
              >
                {sessionStats.user_id}
              </Descriptions.Item>
              <Descriptions.Item label={t("analytics.channel", "Channel")}>
                {sessionStats.channel}
              </Descriptions.Item>
              <Descriptions.Item label={t("analytics.skills", "Skills")}>
                {sessionStats.skills_used.length}
              </Descriptions.Item>
              <Descriptions.Item
                label={t("analytics.firstActive", "First Active")}
                span={1}
              >
                {sessionStats.first_active
                  ? dayjs(sessionStats.first_active).format("YYYY-MM-DD HH:mm")
                  : "-"}
              </Descriptions.Item>
              <Descriptions.Item
                label={t("analytics.lastActive", "Last Active")}
                span={1}
              >
                {sessionStats.last_active
                  ? dayjs(sessionStats.last_active).format("YYYY-MM-DD HH:mm")
                  : "-"}
              </Descriptions.Item>
            </Descriptions>

            {/* 模型使用 */}
            {sessionStats.model_usage.length > 0 && (
              <div className={styles.section}>
                <h4>
                  <Cpu size={14} />
                  {t("analytics.modelUsage", "Model Usage")}
                </h4>
                <div className={styles.tagList}>
                  {sessionStats.model_usage.map((m) => (
                    <Tag key={m.model_name}>
                      {m.model_name}: {m.count}
                    </Tag>
                  ))}
                </div>
              </div>
            )}

            {/* 技能使用 */}
            {sessionStats.skills_used.length > 0 && (
              <div className={styles.section}>
                <h4>
                  <Zap size={14} />
                  {t("analytics.skillsUsed", "Skills Used")}
                </h4>
                <div className={styles.tagList}>
                  {sessionStats.skills_used.map((s) => (
                    <Tag key={s.skill_name} color="blue">
                      {s.skill_name}: {s.count}
                    </Tag>
                  ))}
                </div>
              </div>
            )}

            {/* MCP 工具使用 */}
            {sessionStats.mcp_tools_used &&
              sessionStats.mcp_tools_used.length > 0 && (
                <div className={styles.section}>
                  <h4>
                    <Plug size={14} />
                    {t("analytics.mcpToolsUsed", "MCP Tools Used")}
                  </h4>
                  <div className={styles.tagList}>
                    {sessionStats.mcp_tools_used.map((mcpTool) => (
                      <Tag
                        key={`${mcpTool.mcp_server}-${mcpTool.tool_name}`}
                        color="geekblue"
                      >
                        {mcpTool.mcp_server}/{mcpTool.tool_name}:{" "}
                        {mcpTool.count}
                      </Tag>
                    ))}
                  </div>
                </div>
              )}

            {/* 对话列表 */}
            <div className={styles.section}>
              <h4>
                <FileText size={14} />
                {t("analytics.traces", "Traces")} ({tracesTotal})
              </h4>

              {tracesLoading ? (
                <div className={styles.loading}>
                  <Spin />
                </div>
              ) : traces.length > 0 ? (
                <div className={styles.tracesList}>
                  {traces.map((trace) => (
                    <div
                      key={trace.trace_id}
                      className={`${styles.traceItem} ${
                        selectedTrace?.trace_id === trace.trace_id
                          ? styles.active
                          : ""
                      }`}
                      onClick={() => fetchTraceDetail(trace)}
                    >
                      <div className={styles.traceHeader}>
                        <span className={styles.traceId}>
                          {trace.trace_id.slice(0, 8)}...
                        </span>
                        <Tag color={getStatusColor(trace.status)}>
                          {trace.status}
                        </Tag>
                      </div>
                      <div className={styles.traceMeta}>
                        <span>
                          {dayjs(trace.start_time).format("HH:mm:ss")}
                        </span>
                        <span>{formatDuration(trace.duration_ms)}</span>
                        <span>{formatTokens(trace.total_tokens)} tokens</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <Empty description={t("analytics.noTraces", "No traces")} />
              )}
            </div>

            {/* 对话详情 */}
            {selectedTrace && traceDetail && (
              <div className={styles.section}>
                {/* 用户输入 */}
                {traceDetail.trace.user_message && (
                  <div className={styles.userMessageSection}>
                    <h4>
                      <User size={14} />
                      {t("analytics.userInput", "User Input")}
                    </h4>
                    <div className={styles.userMessageContent}>
                      {traceDetail.trace.user_message}
                    </div>
                  </div>
                )}

                <h4>
                  <Clock size={14} />
                  {t("analytics.traceTimeline", "Trace Timeline")}
                </h4>
                {traceLoading ? (
                  <div className={styles.loading}>
                    <Spin />
                  </div>
                ) : (
                  <Timeline
                    items={traceDetail.spans.slice(0, 10).map((span) => ({
                      color: span.error ? "red" : "blue",
                      children: (
                        <div>
                          <Tag>{span.event_type}</Tag>
                          <span style={{ marginLeft: 8 }}>{span.name}</span>
                          {span.duration_ms && (
                            <span
                              style={{
                                marginLeft: 8,
                                color: "#999",
                                fontSize: 12,
                              }}
                            >
                              {formatDuration(span.duration_ms)}
                            </span>
                          )}
                        </div>
                      ),
                    }))}
                  />
                )}
              </div>
            )}
          </div>
        ) : (
          <Empty />
        )}
      </Drawer>
    </div>
  );
}
