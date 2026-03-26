import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Row, Col, Card, Statistic, Table, Spin, DatePicker, Empty } from "antd";
import {
  Users,
  MessageSquare,
  Zap,
  Clock,
  Cpu,
  BookOpen,
} from "lucide-react";
import type { ColumnsType } from "antd/es/table";
import dayjs from "dayjs";
import { request } from "../../../api";
import styles from "./index.module.less";

const { RangePicker } = DatePicker;

interface OverviewStats {
  online_users: number;
  total_users: number;
  model_distribution: ModelUsage[];
  total_tokens: number;
  input_tokens: number;
  output_tokens: number;
  total_sessions: number;
  total_conversations: number;
  avg_duration_ms: number;
  top_tools: ToolUsage[];
  top_skills: SkillUsage[];
  daily_trend: DailyStats[];
}

interface ModelUsage {
  model_name: string;
  count: number;
  total_tokens: number;
  input_tokens: number;
  output_tokens: number;
}

interface ToolUsage {
  tool_name: string;
  count: number;
  avg_duration_ms: number;
  error_count: number;
}

interface SkillUsage {
  skill_name: string;
  count: number;
  avg_duration_ms: number;
}

interface DailyStats {
  date: string;
  total_users: number;
  active_users: number;
  total_tokens: number;
  session_count: number;
}

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
      const params = new URLSearchParams();
      params.append("start_date", dateRange[0].format("YYYY-MM-DD"));
      params.append("end_date", dateRange[1].format("YYYY-MM-DD"));

      const data = await request<OverviewStats>(
        `/tracing/overview?${params.toString()}`
      );
      setStats(data);
    } catch (error) {
      console.error("Failed to fetch stats:", error);
    } finally {
      setLoading(false);
    }
  };

  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${(ms / 60000).toFixed(1)}m`;
  };

  const formatTokens = (tokens: number) => {
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
        <Empty description={t("analytics.noData", "No analytics data available")} />
      </div>
    );
  }

  return (
    <div className={styles.overviewPage}>
      <div className={styles.header}>
        <h2>{t("analytics.overview", "Overview")}</h2>
        <RangePicker
          value={dateRange}
          onChange={(dates) => dates && setDateRange(dates as [dayjs.Dayjs, dayjs.Dayjs])}
        />
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title={t("analytics.onlineUsers", "Online Users")}
              value={stats.online_users}
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

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={12}>
          <Card
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
    </div>
  );
}
