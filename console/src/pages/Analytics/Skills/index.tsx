import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Card,
  Table,
  Spin,
  DatePicker,
  Tag,
  Progress,
  Tooltip,
  Collapse,
  Button,
  Modal,
} from "antd";
import {
  BookOpen,
  Wrench,
  Plug,
  Target,
} from "lucide-react";
import type { ColumnsType } from "antd/es/table";
import dayjs from "dayjs";
import {
  tracingApi,
  SkillToolsStats,
  ToolAttributionDetail,
} from "../../../api/modules/tracing";
import styles from "./index.module.less";

const { RangePicker } = DatePicker;
const { Panel } = Collapse;

export default function SkillsPage() {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [attributions, setAttributions] = useState<ToolAttributionDetail[]>([]);
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs]>([
    dayjs().subtract(7, "day"),
    dayjs(),
  ]);
  const [skillModalVisible, setSkillModalVisible] = useState(false);
  const [selectedSkill, setSelectedSkill] = useState<string | null>(null);
  const [skillStats, setSkillStats] = useState<SkillToolsStats | null>(null);
  const [skillLoading, setSkillLoading] = useState(false);

  useEffect(() => {
    fetchAttributions();
  }, [dateRange]);

  const fetchAttributions = async () => {
    setLoading(true);
    try {
      const data = await tracingApi.getSkillAttribution({
        start_date: dateRange[0].format("YYYY-MM-DD"),
        end_date: dateRange[1].format("YYYY-MM-DD"),
      });
      setAttributions(data.attributions || []);
    } catch (error) {
      console.error("Failed to fetch skill attributions:", error);
    } finally {
      setLoading(false);
    }
  };

  const fetchSkillStats = async (skillName: string) => {
    setSelectedSkill(skillName);
    setSkillModalVisible(true);
    setSkillLoading(true);
    try {
      const stats = await tracingApi.getSkillToolsStats(
        skillName,
        dateRange[0].format("YYYY-MM-DD"),
        dateRange[1].format("YYYY-MM-DD")
      );
      setSkillStats(stats);
    } catch (error) {
      console.error("Failed to fetch skill stats:", error);
    } finally {
      setSkillLoading(false);
    }
  };

  const formatTokens = (tokens: number) => {
    if (!tokens) return "0";
    if (tokens < 1000) return tokens.toString();
    if (tokens < 1000000) return `${(tokens / 1000).toFixed(1)}K`;
    return `${(tokens / 1000000).toFixed(2)}M`;
  };

  const attributionColumns: ColumnsType<ToolAttributionDetail> = [
    {
      title: t("analytics.toolName", "Tool Name"),
      dataIndex: "tool_name",
      key: "tool_name",
      width: 200,
      render: (name) => (
        <Tag icon={<Wrench size={14} />} color="blue">
          {name}
        </Tag>
      ),
    },
    {
      title: t("analytics.totalCalls", "Total Calls"),
      dataIndex: "total_calls",
      key: "total_calls",
      width: 100,
      sorter: (a, b) => a.total_calls - b.total_calls,
    },
    {
      title: t("analytics.skillAttribution", "Skill Attribution"),
      dataIndex: "skill_attribution",
      key: "skill_attribution",
      render: (attr) => {
        const skills = Object.values(attr) as Array<{
          skill_name: string;
          calls: number;
          weight: number;
          confidence: number;
        }>;
        return (
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {skills.map((s) => (
              <Tooltip
                key={s.skill_name}
                title={`${t("analytics.calls", "Calls")}: ${s.calls}, ${t("analytics.confidence", "Confidence")}: ${(s.confidence * 100).toFixed(0)}%`}
              >
                <Tag
                  icon={<BookOpen size={14} />}
                  color={s.weight > 0.5 ? "green" : "orange"}
                  onClick={() => fetchSkillStats(s.skill_name)}
                  style={{ cursor: "pointer" }}
                >
                  {s.skill_name} ({(s.weight * 100).toFixed(0)}%)
                </Tag>
              </Tooltip>
            ))}
          </div>
        );
      },
    },
    {
      title: t("analytics.avgConfidence", "Avg Confidence"),
      dataIndex: "avg_confidence",
      key: "avg_confidence",
      width: 150,
      render: (conf) => (
        <Progress
          percent={Math.round(conf * 100)}
          size="small"
          status={conf > 0.8 ? "success" : conf > 0.5 ? "normal" : "exception"}
        />
      ),
      sorter: (a, b) => a.avg_confidence - b.avg_confidence,
    },
    {
      title: t("analytics.ambiguous", "Ambiguous"),
      dataIndex: "ambiguous_calls",
      key: "ambiguous_calls",
      width: 100,
      render: (count) => (
        <Tag color={count > 0 ? "warning" : "default"}>
          {count}
        </Tag>
      ),
    },
  ];

  const toolColumns = [
    {
      title: t("analytics.toolName", "Tool Name"),
      dataIndex: "tool_name",
      key: "tool_name",
    },
    {
      title: t("analytics.calls", "Calls"),
      dataIndex: "count",
      key: "count",
      sorter: (a: any, b: any) => a.count - b.count,
    },
    {
      title: t("analytics.avgDuration", "Avg Duration"),
      dataIndex: "avg_duration_ms",
      key: "avg_duration_ms",
      render: (ms: number) => ms ? `${ms}ms` : "-",
    },
    {
      title: t("analytics.type", "Type"),
      dataIndex: "is_mcp",
      key: "is_mcp",
      render: (isMcp: boolean, record: any) => (
        <Tag
          icon={isMcp ? <Plug size={14} /> : <Wrench size={14} />}
          color={isMcp ? "purple" : "blue"}
        >
          {isMcp ? `MCP (${record.mcp_server})` : "Built-in"}
        </Tag>
      ),
    },
  ];

  return (
    <div className={styles.skillsPage}>
      <div className={styles.header}>
        <h2>
          <BookOpen size={24} style={{ marginRight: 8 }} />
          {t("analytics.skillAttribution", "Skill Attribution")}
        </h2>
        <RangePicker
          value={dateRange}
          onChange={(dates) => setDateRange(dates as [dayjs.Dayjs, dayjs.Dayjs])}
          allowClear
        />
      </div>

      <Spin spinning={loading}>
        <Card>
          <Table
            dataSource={attributions}
            columns={attributionColumns}
            rowKey="tool_name"
            pagination={{
              pageSize: 20,
              showSizeChanger: true,
            }}
          />
        </Card>
      </Spin>

      <Modal
        title={
          <span>
            <BookOpen size={18} style={{ marginRight: 8 }} />
            {selectedSkill} - {t("analytics.toolsUsed", "Tools Used")}
          </span>
        }
        open={skillModalVisible}
        onCancel={() => {
          setSkillModalVisible(false);
          setSelectedSkill(null);
          setSkillStats(null);
        }}
        footer={null}
        width={700}
      >
        <Spin spinning={skillLoading}>
          {skillStats && (
            <div>
              <Card size="small" style={{ marginBottom: 16 }}>
                <div style={{ display: "flex", gap: 24 }}>
                  <div>
                    <span style={{ color: "#666" }}>{t("analytics.totalCalls", "Total Calls")}: </span>
                    <strong>{skillStats.total_calls}</strong>
                  </div>
                  <div>
                    <span style={{ color: "#666" }}>{t("analytics.avgDuration", "Avg Duration")}: </span>
                    <strong>{skillStats.avg_duration_ms}ms</strong>
                  </div>
                  <div>
                    <span style={{ color: "#666" }}>{t("analytics.successRate", "Success Rate")}: </span>
                    <Progress
                      percent={Math.round(skillStats.success_rate * 100)}
                      size="small"
                      style={{ width: 100 }}
                    />
                  </div>
                  <div>
                    <span style={{ color: "#666" }}>{t("analytics.avgConfidence", "Avg Confidence")}: </span>
                    <Progress
                      percent={Math.round(skillStats.avg_confidence * 100)}
                      size="small"
                      status={skillStats.avg_confidence > 0.8 ? "success" : "normal"}
                      style={{ width: 100 }}
                    />
                  </div>
                </div>
              </Card>

              <Collapse defaultActiveKey={["tools", "reasons"]}>
                <Panel
                  header={
                    <span>
                      <Wrench size={16} style={{ marginRight: 8 }} />
                      {t("analytics.toolsUsed", "Tools Used")} ({skillStats.tools_used?.length || 0})
                    </span>
                  }
                  key="tools"
                >
                  <Table
                    dataSource={skillStats.tools_used || []}
                    columns={toolColumns}
                    rowKey="tool_name"
                    size="small"
                    pagination={false}
                  />
                </Panel>

                <Panel
                  header={
                    <span>
                      <Target size={16} style={{ marginRight: 8 }} />
                      {t("analytics.triggerReasons", "Trigger Reasons")}
                    </span>
                  }
                  key="reasons"
                >
                  <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                    {Object.entries(skillStats.trigger_reasons || {}).map(([reason, count]) => (
                      <Tag key={reason} color={reason === "declared" ? "green" : reason === "inferred" ? "orange" : "blue"}>
                        {reason}: {count}
                      </Tag>
                    ))}
                  </div>
                </Panel>

                {skillStats.mcp_servers_used?.length > 0 && (
                  <Panel
                    header={
                      <span>
                        <Plug size={16} style={{ marginRight: 8 }} />
                        {t("analytics.mcpServers", "MCP Servers")}
                      </span>
                    }
                    key="mcp"
                  >
                    <div style={{ display: "flex", gap: 12 }}>
                      {skillStats.mcp_servers_used.map((server) => (
                        <Tag key={server} icon={<Plug size={14} />} color="purple">
                          {server}
                        </Tag>
                      ))}
                    </div>
                  </Panel>
                )}
              </Collapse>
            </div>
          )}
        </Spin>
      </Modal>
    </div>
  );
}