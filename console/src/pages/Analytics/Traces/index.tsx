import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Table, Card, Input, Select, Button, Tag, Drawer, Descriptions, Timeline, Spin, Empty, DatePicker } from "antd";
import { FileText, Clock, Zap } from "lucide-react";
import type { ColumnsType } from "antd/es/table";
import dayjs from "dayjs";
import { tracingApi, TraceDetail } from "../../../api/modules/tracing";
import styles from "./index.module.less";

const { RangePicker } = DatePicker;

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
  skills_count: number;
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
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(
    null,
  );
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedTrace, setSelectedTrace] = useState<TraceDetail | null>(null);
  const [traceLoading, setTraceLoading] = useState(false);

  useEffect(() => {
    fetchTraces();
  }, [page, pageSize, statusFilter, dateRange]);

  const fetchTraces = async () => {
    setLoading(true);
    try {
      const data = await tracingApi.getTraces(page, pageSize, {
        user_id: userIdFilter || undefined,
        status: statusFilter,
        start_date: dateRange?.[0]?.format("YYYY-MM-DD"),
        end_date: dateRange?.[1]?.format("YYYY-MM-DD"),
      });
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
      const data = await tracingApi.getTraceDetail(traceId);
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

  const handleDateChange = (dates: [dayjs.Dayjs, dayjs.Dayjs] | null) => {
    setDateRange(dates);
    setPage(1);
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
      width: 280,
      ellipsis: true,
      render: (v) => (
        <span style={{ cursor: "pointer", color: "#1890ff", fontFamily: "monospace" }}>
          {v}
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
      width: 160,
      render: (v) => dayjs(v).format("YYYY-MM-DD HH:mm:ss"),
    },
    {
      title: t("analytics.duration", "Duration"),
      dataIndex: "duration_ms",
      key: "duration_ms",
      width: 100,
      render: (v) => formatDuration(v),
    },
    {
      title: t("analytics.model", "Model"),
      dataIndex: "model_name",
      key: "model_name",
      width: 150,
      ellipsis: true,
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
      dataIndex: "skills_count",
      key: "skills_count",
      width: 60,
    },
    {
      title: t("analytics.status", "Status"),
      dataIndex: "status",
      key: "status",
      width: 90,
      render: (v) => <Tag color={getStatusColor(v)}>{v}</Tag>,
    },
  ];

  return (
    <div className={styles.tracesPage}>
      <div className={styles.header}>
        <h2>{t("analytics.traceDetails", "Trace Details")}</h2>
        <div className={styles.filters}>
          <RangePicker
            value={dateRange}
            onChange={(dates) =>
              handleDateChange(dates as [dayjs.Dayjs, dayjs.Dayjs] | null)
            }
            allowClear
          />
          <Input
            placeholder={t("analytics.searchUser", "Search user...")}
            value={userIdFilter}
            onChange={(e) => setUserIdFilter(e.target.value)}
            onPressEnter={handleSearch}
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
          <Button type="primary" onClick={handleSearch}>
            {t("common.search", "Search")}
          </Button>
        </div>
      </div>

      <Card>
        <Table
          dataSource={traces}
          columns={columns}
          rowKey="trace_id"
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
            overflowX: "hidden",
            padding: "16px",
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
              <Descriptions.Item
                label={t("analytics.traceId", "Trace ID")}
                span={2}
              >
                <code>{selectedTrace.trace.trace_id}</code>
              </Descriptions.Item>
              <Descriptions.Item label={t("analytics.userId", "User ID")}>
                {selectedTrace.trace.user_id}
              </Descriptions.Item>
              <Descriptions.Item label={t("analytics.channel", "Channel")}>
                {selectedTrace.trace.channel}
              </Descriptions.Item>
              <Descriptions.Item label={t("analytics.startTime", "Start Time")}>
                {dayjs(selectedTrace.trace.start_time).format(
                  "YYYY-MM-DD HH:mm:ss",
                )}
              </Descriptions.Item>
              <Descriptions.Item label={t("analytics.duration", "Duration")}>
                {formatDuration(selectedTrace.trace.duration_ms)}
              </Descriptions.Item>
              <Descriptions.Item
                label={t("analytics.totalTokens", "Total Tokens")}
              >
                {formatTokens(
                  selectedTrace.trace.total_input_tokens +
                    selectedTrace.trace.total_output_tokens,
                )}
                <span style={{ color: "#999", marginLeft: 8 }}>
                  (in: {formatTokens(selectedTrace.trace.total_input_tokens)},
                  out: {formatTokens(selectedTrace.trace.total_output_tokens)})
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
                <pre className={styles.errorText}>
                  {selectedTrace.trace.error}
                </pre>
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
                      {span.input_tokens != null && span.input_tokens > 0 && (
                        <div className={styles.timelineDetail}>
                          <strong>Input tokens:</strong> {span.input_tokens}
                        </div>
                      )}
                      {span.output_tokens != null && span.output_tokens > 0 && (
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
                        <Descriptions.Item
                          label={t("analytics.duration", "Duration")}
                        >
                          {formatDuration(tool.duration_ms)}
                        </Descriptions.Item>
                      )}
                      {tool.error && (
                        <Descriptions.Item
                          label={t("analytics.error", "Error")}
                        >
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
