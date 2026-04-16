import { useEffect, useState, useRef } from "react";
import { useTranslation } from "react-i18next";
import {
  Table,
  Card,
  Input,
  Button,
  DatePicker,
  Tooltip,
  message,
} from "antd";
import { Download } from "lucide-react";
import type { ColumnsType } from "antd/es/table";
import dayjs from "dayjs";
import { tracingApi, UserMessageItem } from "../../../api/modules/tracing";
import styles from "./index.module.less";

const { RangePicker } = DatePicker;

export default function MessagesPage() {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [messages, setMessages] = useState<UserMessageItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [searchQuery, setSearchQuery] = useState("");
  const [userIdFilter, setUserIdFilter] = useState("");
  const [sessionIdFilter, setSessionIdFilter] = useState("");
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(
    [dayjs().subtract(7, "day"), dayjs()],
  );
  const [exporting, setExporting] = useState(false);

  // 用于追踪筛选条件变化，避免 useEffect 重复触发
  const filtersRef = useRef({
    searchQuery: "",
    userIdFilter: "",
    sessionIdFilter: "",
    dateRange: null as [dayjs.Dayjs, dayjs.Dayjs] | null,
  });

  useEffect(() => {
    // 检查筛选条件是否变化
    const filtersChanged =
      filtersRef.current.searchQuery !== searchQuery ||
      filtersRef.current.userIdFilter !== userIdFilter ||
      filtersRef.current.sessionIdFilter !== sessionIdFilter ||
      filtersRef.current.dateRange !== dateRange;

    // 更新 ref
    filtersRef.current = {
      searchQuery,
      userIdFilter,
      sessionIdFilter,
      dateRange,
    };

    // 如果筛选条件变化且不是第一页，只重置页码不查询（等待 page 变化触发查询）
    if (filtersChanged && page !== 1) {
      setPage(1);
      return;
    }

    fetchMessages();
  }, [page, pageSize, dateRange]);

  const handleSearch = () => {
    setPage(1);
    fetchMessages();
  };

  const fetchMessages = async () => {
    setLoading(true);
    try {
      const data = await tracingApi.getUserMessages(page, pageSize, {
        user_id: userIdFilter || undefined,
        session_id: sessionIdFilter || undefined,
        start_date: dateRange?.[0]?.format("YYYY-MM-DD"),
        end_date: dateRange?.[1]?.format("YYYY-MM-DD"),
        query: searchQuery || undefined,
      });
      setMessages(data.items || []);
      setTotal(data.total || 0);
    } catch (error) {
      console.error("Failed to fetch messages:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      const blob = await tracingApi.exportUserMessages(
        {
          user_id: userIdFilter || undefined,
          session_id: sessionIdFilter || undefined,
          start_date: dateRange?.[0]?.format("YYYY-MM-DD"),
          end_date: dateRange?.[1]?.format("YYYY-MM-DD"),
          query: searchQuery || undefined,
        },
        "xlsx",
      );
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `user_messages_${dayjs().format("YYYYMMDD_HHmmss")}.xlsx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Failed to export messages:", error);
      const errorMsg = error instanceof Error ? error.message : "Export failed";
      message.error(errorMsg);
    } finally {
      setExporting(false);
    }
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

  const truncateMessage = (msg: string | null, maxLen: number = 100) => {
    if (!msg) return "-";
    if (msg.length <= maxLen) return msg;
    return msg.slice(0, maxLen) + "...";
  };

  const columns: ColumnsType<UserMessageItem> = [
    {
      title: t("analytics.traceId", "Trace ID"),
      dataIndex: "trace_id",
      key: "trace_id",
      width: 200,
      ellipsis: true,
      render: (v) => (
        <Tooltip title={v}>
          <span style={{ fontFamily: "monospace", fontSize: 12 }}>
            {v}
          </span>
        </Tooltip>
      ),
    },
    {
      title: t("analytics.userId", "User ID"),
      dataIndex: "user_id",
      key: "user_id",
      width: 100,
      ellipsis: true,
    },
    {
      title: t("analytics.sessionId", "Session ID"),
      dataIndex: "session_id",
      key: "session_id",
      width: 120,
      ellipsis: true,
    },
    {
      title: t("analytics.userMessage", "User Message"),
      dataIndex: "user_message",
      key: "user_message",
      width: 380,
      render: (msg) => {
        if (!msg) return <span style={{ color: "#999" }}>-</span>;
        const truncated = truncateMessage(msg, 150);
        if (msg.length <= 150) {
          return <span className={styles.userMessage}>{msg}</span>;
        }
        return (
          <Tooltip
            title={<pre className={styles.messagePopover}>{msg}</pre>}
            overlayStyle={{ maxWidth: 500 }}
          >
            <span className={styles.userMessage}>{truncated}</span>
          </Tooltip>
        );
      },
    },
    {
      title: t("analytics.inputTokens", "Input"),
      dataIndex: "input_tokens",
      key: "input_tokens",
      width: 80,
      render: (v) => formatTokens(v),
    },
    {
      title: t("analytics.outputTokens", "Output"),
      dataIndex: "output_tokens",
      key: "output_tokens",
      width: 80,
      render: (v) => formatTokens(v),
    },
    {
      title: t("analytics.model", "Model"),
      dataIndex: "model_name",
      key: "model_name",
      width: 150,
      ellipsis: true,
      render: (v) => v || "-",
    },
    {
      title: t("analytics.startTime", "Start Time"),
      dataIndex: "start_time",
      key: "start_time",
      width: 150,
      render: (v) => dayjs(v).format("YYYY-MM-DD HH:mm:ss"),
    },
    {
      title: t("analytics.duration", "Duration"),
      dataIndex: "duration_ms",
      key: "duration_ms",
      width: 80,
      render: (v) => formatDuration(v),
    },
  ];

  return (
    <div className={styles.messagesPage}>
      <div className={styles.header}>
        <h2>{t("analytics.userMessages", "User Messages")}</h2>
        <RangePicker
          value={dateRange}
          onChange={(dates) =>
            setDateRange(dates as [dayjs.Dayjs, dayjs.Dayjs] | null)
          }
          allowClear
        />
      </div>

      <div className={styles.toolbar}>
        <div className={styles.searchBox}>
          <Input
            placeholder={t("analytics.searchMessage", "Search messages...")}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onPressEnter={handleSearch}
            allowClear
          />
        </div>
        <div className={styles.filters}>
          <Input
            placeholder={t("analytics.filterUser", "User ID")}
            value={userIdFilter}
            onChange={(e) => setUserIdFilter(e.target.value)}
            onPressEnter={handleSearch}
            style={{ width: 150 }}
            allowClear
          />
          <Input
            placeholder={t("analytics.filterSession", "Session ID")}
            value={sessionIdFilter}
            onChange={(e) => setSessionIdFilter(e.target.value)}
            onPressEnter={handleSearch}
            style={{ width: 200 }}
            allowClear
          />
          <Button type="primary" onClick={handleSearch}>
            {t("common.search", "Search")}
          </Button>
          <Button
            icon={<Download size={16} />}
            onClick={handleExport}
            loading={exporting}
            style={{ minWidth: 120 }}
          >
            {t("analytics.exportExcel", "Export Excel")}
          </Button>
        </div>
      </div>

      <Card>
        <Table
          dataSource={messages}
          columns={columns}
          rowKey="trace_id"
          loading={loading}
          scroll={{ x: 1200 }}
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
        />
      </Card>
    </div>
  );
}
