import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Table, Card, Input, Select, Tag, Drawer, Descriptions, Timeline, Spin, Empty } from "antd";
import { FileText, Clock, Zap } from "lucide-react";
import type { ColumnsType } from "antd/es/table";
import dayjs from "dayjs";
import { request } from "../../../api";
import styles from "./index.module.less";

const { Search: SearchInput } = Input;

interface TraceListItem {
  trace_id: string;
  user_id: string;
  session_id: string;
  channel: string;
  start_time: string;
  duration_ms: number | null;
  total_tokens: number;
  model_name: string | null;
  status: string;
  tools_count: number;
}

interface TraceDetail {
  trace: Trace;
  spans: Span[];
  llm_duration_ms: number;
  tool_duration_ms: number;
  tools_called: ToolCall[];
}

interface Trace {
  trace_id: string;
  user_id: string;
  session_id: string;
  channel: string;
  start_time: string;
  end_time: string | null;
  duration_ms: number | null;
  model_name: string | null;
  total_input_tokens: number;
  total_output_tokens: number;
  tools_used: string[];
  skills_used: string[];
  status: string;
  error: string | null;
}

interface Span {
  span_id: string;
  trace_id: string;
  name: string;
  event_type: string;
  start_time: string;
  end_time: string | null;
  duration_ms: number | null;
  model_name: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  tool_name: string | null;
  skill_name: string | null;
  tool_input: Record<string, unknown> | null;
  tool_output: string | null;
  error: string | null;
}

interface ToolCall {
  tool_name: string;
  tool_input: Record<string, unknown> | null;
  tool_output: string | null;
  duration_ms: number | null;
  error: string | null;
}

interface TracesResponse {
  items: TraceListItem[];
  total: number;
  page: number;
  page_size: number;
}

export default function TracesPage() {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [traces, setTraces] = useState<TraceListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [userIdFilter, setUserIdFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedTrace, setSelectedTrace] = useState<TraceDetail | null>(null);
  const [traceLoading, setTraceLoading] = useState(false);

  useEffect(() => {
    fetchTraces();
  }, [page, pageSize, statusFilter]);

  const fetchTraces = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.append("page", page.toString());
      params.append("page_size", pageSize.toString());
      if (userIdFilter) {
        params.append("user_id", userIdFilter);
      }
      if (statusFilter) {
        params.append("status", statusFilter);
      }

      const data = await request<TracesResponse>(`/tracing/traces?${params.toString()}`);
      setTraces(data.items || []);
      setTotal(data.total || 0);
    } catch (error) {
      console.error("Failed to fetch traces:", error);
    } finally {
      setLoading(false);
    }
  };

  const fetchTraceDetail = async (traceId: string) => {
    setTraceLoading(true);
    try {
      const data = await request<TraceDetail>(`/tracing/traces/${traceId}`);
      setSelectedTrace(data);
    } catch (error) {
      console.error("Failed to fetch trace detail:", error);
    } finally {
      setTraceLoading(false);
    }
  };

  const handleRowClick = (record: TraceListItem) => {
    setDrawerOpen(true);
    fetchTraceDetail(record.trace_id);
  };

  const handleSearch = () => {
    setPage(1);
    fetchTraces();
  };

  const formatDuration = (ms: number | null) => {
    if (ms === null) return "-";
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${(ms / 60000).toFixed(1)}m`;
  };

  const formatTokens = (tokens: number) => {
    if (tokens < 1000) return tokens.toString();
    if (tokens < 1000000) return `${(tokens / 1000).toFixed(1)}K`;
    return `${(tokens / 1000000).toFixed(2)}M`;
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

  const columns: ColumnsType<TraceListItem> = [
    {
      title: t("analytics.traceId", "Trace ID"),
      dataIndex: "trace_id",
      key: "trace_id",
      width: 120,
      render: (v) => (
        <span style={{ cursor: "pointer", color: "#1890ff", fontFamily: "monospace" }}>
          {v.slice(0, 8)}...
        </span>
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
      title: t("analytics.startTime", "Start Time"),
      dataIndex: "start_time",
      key: "start_time",
      width: 130,
      render: (v) => dayjs(v).format("MM-DD HH:mm:ss"),
    },
    {
      title: t("analytics.duration", "Duration"),
      dataIndex: "duration_ms",
      key: "duration_ms",
      width: 80,
      render: (v) => formatDuration(v),
    },
    {
      title: t("analytics.model", "Model"),
      dataIndex: "model_name",
      key: "model_name",
      width: 120,
      ellipsis: true,
    },
    {
      title: t("analytics.tokens", "Tokens"),
      dataIndex: "total_tokens",
      key: "total_tokens",
      width: 100,
      render: (v) => formatTokens(v),
    },
    {
      title: t("analytics.tools", "Tools"),
      dataIndex: "tools_count",
      key: "tools_count",
      width: 80,
    },
    {
      title: t("analytics.status", "Status"),
      dataIndex: "status",
      key: "status",
      width: 100,
      render: (v) => <Tag color={getStatusColor(v)}>{v}</Tag>,
    },
  ];

  return (
    <div className={styles.tracesPage}>
      <div className={styles.header}>
        <h2>{t("analytics.traceDetails", "Trace Details")}</h2>
        <div className={styles.filters}>
          <SearchInput
            placeholder={t("analytics.searchUser", "Search user...")}
            value={userIdFilter}
            onChange={(e) => setUserIdFilter(e.target.value)}
            onSearch={handleSearch}
            style={{ width: 200 }}
            allowClear
          />
          <Select
            placeholder={t("analytics.filterStatus", "Filter status")}
            value={statusFilter}
            onChange={(v) => {
              setStatusFilter(v);
              setPage(1);
            }}
            allowClear
            style={{ width: 150 }}
            options={[
              { value: "completed", label: "Completed" },
              { value: "running", label: "Running" },
              { value: "error", label: "Error" },
              { value: "cancelled", label: "Cancelled" },
            ]}
          />
        </div>
      </div>

      <Card className={styles.tableCard}>
        <Table
          dataSource={traces}
          columns={columns}
          rowKey="trace_id"
          loading={loading}
          scroll={{ x: 850 }}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            showTotal: (total) => t("analytics.totalItems", { total }),
            onChange: (p, ps) => {
              setPage(p);
              setPageSize(ps);
            },
          }}
          onRow={(record) => ({
            onClick: () => handleRowClick(record),
            style: { cursor: "pointer" },
          })}
        />
      </Card>

      <Drawer
        title={
          <span>
            <FileText size={18} style={{ marginRight: 8 }} />
            {t("analytics.traceDetail", "Trace Detail")}
          </span>
        }
        placement="right"
        width={700}
        open={drawerOpen}
        onClose={() => {
          setDrawerOpen(false);
          setSelectedTrace(null);
        }}
        styles={{
          body: {
            overflowX: 'hidden',
            padding: '16px',
          },
        }}
      >
        {traceLoading ? (
          <div className={styles.drawerLoading}>
            <Spin />
          </div>
        ) : selectedTrace ? (
          <div className={styles.drawerContent}>
            <Descriptions column={2} bordered size="small">
              <Descriptions.Item label={t("analytics.traceId", "Trace ID")} span={2}>
                <code>{selectedTrace.trace.trace_id}</code>
              </Descriptions.Item>
              <Descriptions.Item label={t("analytics.userId", "User ID")}>
                {selectedTrace.trace.user_id}
              </Descriptions.Item>
              <Descriptions.Item label={t("analytics.channel", "Channel")}>
                {selectedTrace.trace.channel}
              </Descriptions.Item>
              <Descriptions.Item label={t("analytics.startTime", "Start Time")}>
                {dayjs(selectedTrace.trace.start_time).format("YYYY-MM-DD HH:mm:ss")}
              </Descriptions.Item>
              <Descriptions.Item label={t("analytics.duration", "Duration")}>
                {formatDuration(selectedTrace.trace.duration_ms)}
              </Descriptions.Item>
              <Descriptions.Item label={t("analytics.totalTokens", "Total Tokens")}>
                {formatTokens(selectedTrace.trace.total_input_tokens + selectedTrace.trace.total_output_tokens)}
                <span style={{ color: "#999", marginLeft: 8 }}>
                  (in: {formatTokens(selectedTrace.trace.total_input_tokens)}, out: {formatTokens(selectedTrace.trace.total_output_tokens)})
                </span>
              </Descriptions.Item>
              <Descriptions.Item label={t("analytics.status", "Status")}>
                <Tag color={getStatusColor(selectedTrace.trace.status)}>
                  {selectedTrace.trace.status}
                </Tag>
              </Descriptions.Item>
            </Descriptions>

            {selectedTrace.trace.error && (
              <div className={styles.errorSection}>
                <h4>{t("analytics.error", "Error")}</h4>
                <pre className={styles.errorText}>{selectedTrace.trace.error}</pre>
              </div>
            )}

            <div className={styles.timelineSection}>
              <h4>
                <Clock size={16} style={{ marginRight: 8 }} />
                {t("analytics.timeline", "Timeline")}
              </h4>
              <Timeline
                items={selectedTrace.spans.map((span) => ({
                  color: span.error ? "red" : "blue",
                  children: (
                    <div className={styles.timelineItem}>
                      <div className={styles.timelineHeader}>
                        <Tag>{span.event_type}</Tag>
                        <span className={styles.timelineName}>{span.name}</span>
                        {span.duration_ms && (
                          <span className={styles.timelineDuration}>
                            {formatDuration(span.duration_ms)}
                          </span>
                        )}
                      </div>
                      {span.tool_name && (
                        <div className={styles.timelineDetail}>
                          <strong>Tool:</strong> {span.tool_name}
                        </div>
                      )}
                      {span.model_name && (
                        <div className={styles.timelineDetail}>
                          <strong>Model:</strong> {span.model_name}
                        </div>
                      )}
                      {span.input_tokens && (
                        <div className={styles.timelineDetail}>
                          <strong>Input tokens:</strong> {span.input_tokens}
                        </div>
                      )}
                      {span.output_tokens && (
                        <div className={styles.timelineDetail}>
                          <strong>Output tokens:</strong> {span.output_tokens}
                        </div>
                      )}
                    </div>
                  ),
                }))}
              />
            </div>

            {selectedTrace.tools_called.length > 0 && (
              <div className={styles.toolsSection}>
                <h4>
                  <Zap size={16} style={{ marginRight: 8 }} />
                  {t("analytics.toolsCalled", "Tools Called")}
                </h4>
                {selectedTrace.tools_called.map((tool, idx) => (
                  <Card key={idx} size="small" style={{ marginBottom: 8 }}>
                    <Descriptions column={1} size="small">
                      <Descriptions.Item label={t("analytics.tool", "Tool")}>
                        {tool.tool_name}
                      </Descriptions.Item>
                      {tool.duration_ms && (
                        <Descriptions.Item label={t("analytics.duration", "Duration")}>
                          {formatDuration(tool.duration_ms)}
                        </Descriptions.Item>
                      )}
                      {tool.error && (
                        <Descriptions.Item label={t("analytics.error", "Error")}>
                          <span style={{ color: "#ff4d4f" }}>{tool.error}</span>
                        </Descriptions.Item>
                      )}
                    </Descriptions>
                  </Card>
                ))}
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
