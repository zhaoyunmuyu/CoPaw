import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Row,
  Col,
  Card,
  Statistic,
  Table,
  Spin,
  DatePicker,
  Empty,
  Tag,
  Collapse,
} from "antd";
import {
  Users,
  MessageSquare,
  Zap,
  Clock,
  Cpu,
  BookOpen,
  Plug,
  Wrench,
} from "lucide-react";
import type { ColumnsType } from "antd/es/table";
import dayjs from "dayjs";
import {
  tracingApi,
  OverviewStats,
  ModelUsage,
  ToolUsage,
  SkillUsage,
  MCPToolUsage,
  MCPServerUsage,
} from "../../../api/modules/tracing";
import styles from "./index.module.less";

const { RangePicker } = DatePicker;
const { Panel } = Collapse;

export default function OverviewPage() {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<OverviewStats | null>(null);
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs]>([
    dayjs().subtract(7, "day"),
    dayjs(),
  ]);

  useEffect(() => {
    fetchStats();
  }, [dateRange]);

  const fetchStats = async () => {
    setLoading(true);
    try {
      const data = await tracingApi.getOverview(
        dateRange[0].format("YYYY-MM-DD"),
        dateRange[1].format("YYYY-MM-DD"),
      );
      setStats(data);
    } catch (error) {
      console.error("Failed to fetch stats:", error);
    } finally {
      setLoading(false);
    }
  };

  const formatDuration = (ms: number) => {
    if (!ms) return "-";
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${(ms / 60000).toFixed(1)}m`;
  };

  const formatTokens = (tokens: number) => {
    if (!tokens) return "0";
    if (tokens < 1000) return tokens.toString();
    if (tokens < 1000000) return `${(tokens / 1000).toFixed(1)}K`;
    return `${(tokens / 1000000).toFixed(2)}M`;
  };

  const modelColumns: ColumnsType<ModelUsage> = [
    {
      title: t("analytics.model", "Model"),
      dataIndex: "model_name",
      key: "model_name",
    },
    {
      title: t("analytics.calls", "Calls"),
      dataIndex: "count",
      key: "count",
      sorter: (a, b) => a.count - b.count,
    },
    {
      title: t("analytics.tokens", "Tokens"),
      dataIndex: "total_tokens",
      key: "total_tokens",
      render: (v) => formatTokens(v),
      sorter: (a, b) => a.total_tokens - b.total_tokens,
    },
  ];

  const skillColumns: ColumnsType<SkillUsage> = [
    {
      title: t("analytics.skill", "Skill"),
      dataIndex: "skill_name",
      key: "skill_name",
    },
    {
      title: t("analytics.calls", "Calls"),
      dataIndex: "count",
      key: "count",
      sorter: (a, b) => a.count - b.count,
    },
    {
      title: t("analytics.avgDuration", "Avg Duration"),
      dataIndex: "avg_duration_ms",
      key: "avg_duration_ms",
      render: (v) => formatDuration(v),
    },
  ];

  const mcpToolColumns: ColumnsType<MCPToolUsage> = [
    {
      title: t("analytics.mcpServer", "MCP Server"),
      dataIndex: "mcp_server",
      key: "mcp_server",
      width: 120,
      render: (v) => <Tag color="blue">{v}</Tag>,
    },
    {
      title: t("analytics.tool", "Tool"),
      dataIndex: "tool_name",
      key: "tool_name",
    },
    {
      title: t("analytics.calls", "Calls"),
      dataIndex: "count",
      key: "count",
      width: 80,
      sorter: (a, b) => a.count - b.count,
    },
    {
      title: t("analytics.avgDuration", "Avg Duration"),
      dataIndex: "avg_duration_ms",
      key: "avg_duration_ms",
      width: 100,
      render: (v) => formatDuration(v),
    },
    {
      title: t("analytics.errors", "Errors"),
      dataIndex: "error_count",
      key: "error_count",
      width: 80,
      render: (v) => (v > 0 ? <Tag color="red">{v}</Tag> : <span>0</span>),
    },
  ];

  const toolColumns: ColumnsType<ToolUsage> = [
    {
      title: t("analytics.tool", "Tool"),
      dataIndex: "tool_name",
      key: "tool_name",
    },
    {
      title: t("analytics.calls", "Calls"),
      dataIndex: "count",
      key: "count",
      width: 80,
      sorter: (a, b) => a.count - b.count,
    },
    {
      title: t("analytics.avgDuration", "Avg Duration"),
      dataIndex: "avg_duration_ms",
      key: "avg_duration_ms",
      width: 100,
      render: (v) => formatDuration(v),
    },
    {
      title: t("analytics.errors", "Errors"),
      dataIndex: "error_count",
      key: "error_count",
      width: 80,
      render: (v) => (v > 0 ? <Tag color="red">{v}</Tag> : <span>0</span>),
    },
  ];

  if (loading) {
    return (
      <div className={styles.loading}>
        <Spin size="large" />
      </div>
    );
  }

  if (!stats) {
    return (
      <div className={styles.empty}>
        <Empty
          description={t("analytics.noData", "No analytics data available")}
        />
      </div>
    );
  }

  return (
    <div className={styles.overviewPage}>
      <div className={styles.header}>
        <h2>{t("analytics.overview", "Overview")}</h2>
        <RangePicker
          value={dateRange}
          onChange={(dates) =>
            dates && setDateRange(dates as [dayjs.Dayjs, dayjs.Dayjs])
          }
        />
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title={t("analytics.users", "Users")}
              value={stats.online_users}
              suffix={
                <span style={{ fontSize: 14, color: "#999" }}>
                  {" "}
                  / {stats.total_users} (
                  {stats.total_users > 0
                    ? Math.round((stats.online_users / stats.total_users) * 100)
                    : 0}
                  %)
                </span>
              }
              prefix={<Users size={20} />}
              valueStyle={{ color: "#52c41a" }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title={t("analytics.totalSessions", "Total Sessions")}
              value={stats.total_sessions}
              prefix={<MessageSquare size={20} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title={t("analytics.totalTokens", "Total Tokens")}
              value={stats.total_tokens}
              prefix={<Zap size={20} />}
              formatter={(v) => formatTokens(Number(v))}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title={t("analytics.avgDuration", "Avg Duration")}
              value={stats.avg_duration_ms}
              prefix={<Clock size={20} />}
              formatter={(v) => formatDuration(Number(v))}
            />
          </Card>
        </Col>
      </Row>

      <Row
        gutter={[16, 16]}
        style={{ marginTop: 16 }}
        className={styles.tableRow}
      >
        <Col xs={24} lg={12}>
          <Card
            className={styles.tableCard}
            title={
              <span>
                <Cpu size={16} style={{ marginRight: 8 }} />
                {t("analytics.modelDistribution", "Model Distribution")}
              </span>
            }
          >
            <Table
              dataSource={stats.model_distribution}
              columns={modelColumns}
              rowKey="model_name"
              size="small"
              pagination={false}
            />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card
            className={styles.tableCard}
            title={
              <span>
                <BookOpen size={16} style={{ marginRight: 8 }} />
                {t("analytics.topSkills", "Top Skills")}
              </span>
            }
          >
            <Table
              dataSource={stats.top_skills}
              columns={skillColumns}
              rowKey="skill_name"
              size="small"
              pagination={false}
            />
          </Card>
        </Col>
      </Row>

      {/* MCP Tools Section */}
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24}>
          <Card
            title={
              <span>
                <Plug size={16} style={{ marginRight: 8 }} />
                {t("analytics.mcpToolCalls", "MCP Tool Calls")} (
                {stats.mcp_servers?.length || 0})
              </span>
            }
          >
            {stats.mcp_servers && stats.mcp_servers.length > 0 ? (
              <Collapse
                defaultActiveKey={stats.mcp_servers
                  .slice(0, 3)
                  .map((_, i) => `server-${i}`)}
              >
                {stats.mcp_servers.map((server, idx) => (
                  <Panel
                    key={`server-${idx}`}
                    header={
                      <span>
                        <Tag color="geekblue">{server.server_name}</Tag>
                        <span style={{ marginLeft: 8 }}>
                          {server.tool_count} tools · {server.total_calls} calls
                          {server.error_count > 0 && (
                            <Tag color="red" style={{ marginLeft: 8 }}>
                              {server.error_count} errors
                            </Tag>
                          )}
                        </span>
                      </span>
                    }
                  >
                    <Table
                      dataSource={server.tools}
                      columns={mcpToolColumns.filter(
                        (col) => col.key !== "mcp_server",
                      )}
                      rowKey="tool_name"
                      size="small"
                      pagination={false}
                    />
                  </Panel>
                ))}
              </Collapse>
            ) : (
              <Empty
                description={t("analytics.noMCPTools", "No MCP tool calls")}
              />
            )}
          </Card>
        </Col>
      </Row>

      {/* Regular Tools Section */}
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24}>
          <Card
            title={
              <span>
                <Wrench size={16} style={{ marginRight: 8 }} />
                {t("analytics.topTools", "Top Tools")} (non-MCP)
              </span>
            }
          >
            {stats.top_tools && stats.top_tools.length > 0 ? (
              <Table
                dataSource={stats.top_tools}
                columns={toolColumns}
                rowKey="tool_name"
                size="small"
                pagination={false}
              />
            ) : (
              <Empty description={t("analytics.noTools", "No tool calls")} />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}
