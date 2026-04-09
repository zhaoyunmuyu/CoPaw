import { useEffect, useState, useRef } from "react";
import { useTranslation } from "react-i18next";
import { Table, Card, Input, Drawer, Descriptions, Spin, Empty, Tag, DatePicker } from "antd";
import { Search, User } from "lucide-react";
import type { ColumnsType } from "antd/es/table";
import dayjs from "dayjs";
import { tracingApi, UserStats, UserListItem } from "../../../api/modules/tracing";
import styles from "./index.module.less";

const { RangePicker } = DatePicker;

export default function UsersPage() {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [users, setUsers] = useState<UserListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [searchQuery, setSearchQuery] = useState("");
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<UserStats | null>(null);
  const [userLoading, setUserLoading] = useState(false);

  // 用于追踪筛选条件变化，避免 useEffect 重复触发
  const filtersRef = useRef({ searchQuery: "", dateRange: null as [dayjs.Dayjs, dayjs.Dayjs] | null });

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

    fetchUsers();
  }, [page, pageSize, searchQuery, dateRange]);

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const data = await tracingApi.getUsers(page, pageSize, {
        user_id: searchQuery || undefined,
        start_date: dateRange?.[0]?.format("YYYY-MM-DD"),
        end_date: dateRange?.[1]?.format("YYYY-MM-DD"),
      });
      setUsers(data.items || []);
      setTotal(data.total || 0);
    } catch (error) {
      console.error("Failed to fetch users:", error);
    } finally {
      setLoading(false);
    }
  };

  const fetchUserStats = async (userId: string) => {
    setUserLoading(true);
    try {
      const data = await tracingApi.getUserStats(userId);
      setSelectedUser(data);
    } catch (error) {
      console.error("Failed to fetch user stats:", error);
    } finally {
      setUserLoading(false);
    }
  };

  const handleRowClick = (record: UserListItem) => {
    setDrawerOpen(true);
    fetchUserStats(record.user_id);
  };

  const formatTokens = (tokens: number) => {
    if (tokens < 1000) return tokens.toString();
    if (tokens < 1000000) return `${(tokens / 1000).toFixed(1)}K`;
    return `${(tokens / 1000000).toFixed(2)}M`;
  };

  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${(ms / 60000).toFixed(1)}m`;
  };

  const columns: ColumnsType<UserListItem> = [
    {
      title: t("analytics.userId", "User ID"),
      dataIndex: "user_id",
      key: "user_id",
      render: (v) => (
        <span style={{ cursor: "pointer", color: "#1890ff" }}>{v}</span>
      ),
    },
    {
      title: t("analytics.sessions", "Sessions"),
      dataIndex: "total_sessions",
      key: "total_sessions",
      sorter: true,
    },
    {
      title: t("analytics.conversations", "Conversations"),
      dataIndex: "total_conversations",
      key: "total_conversations",
      sorter: true,
    },
    {
      title: t("analytics.tokens", "Tokens"),
      dataIndex: "total_tokens",
      key: "total_tokens",
      render: (v) => formatTokens(v),
      sorter: true,
    },
    {
      title: t("analytics.lastActive", "Last Active"),
      dataIndex: "last_active",
      key: "last_active",
      render: (v) => (v ? dayjs(v).format("YYYY-MM-DD HH:mm") : "-"),
    },
  ];

  return (
    <div className={styles.usersPage}>
      <div className={styles.header}>
        <h2>{t("analytics.userAnalysis", "User Analysis")}</h2>
        <div style={{ display: "flex", gap: 12 }}>
          <RangePicker
            value={dateRange}
            onChange={(dates) => setDateRange(dates as [dayjs.Dayjs, dayjs.Dayjs] | null)}
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
          dataSource={users}
          columns={columns}
          rowKey="user_id"
          loading={loading}
          scroll={{ x: 700 }}
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
            <User size={18} style={{ marginRight: 8 }} />
            {selectedUser?.user_id || t("analytics.userDetails", "User Details")}
          </span>
        }
        placement="right"
        width={600}
        open={drawerOpen}
        onClose={() => {
          setDrawerOpen(false);
          setSelectedUser(null);
        }}
      >
        {userLoading ? (
          <div className={styles.drawerLoading}>
            <Spin />
          </div>
        ) : selectedUser ? (
          <div className={styles.drawerContent}>
            <Descriptions column={2} bordered size="small">
              <Descriptions.Item label={t("analytics.totalSessions", "Total Sessions")} span={1}>
                {selectedUser.total_sessions}
              </Descriptions.Item>
              <Descriptions.Item label={t("analytics.conversations", "Conversations")} span={1}>
                {selectedUser.total_conversations}
              </Descriptions.Item>
              <Descriptions.Item label={t("analytics.totalTokens", "Total Tokens")} span={1}>
                {formatTokens(selectedUser.total_tokens)}
              </Descriptions.Item>
              <Descriptions.Item label={t("analytics.avgDuration", "Avg Duration")} span={1}>
                {formatDuration(selectedUser.avg_duration_ms)}
              </Descriptions.Item>
              <Descriptions.Item label={t("analytics.inputTokens", "Input Tokens")} span={1}>
                {formatTokens(selectedUser.input_tokens)}
              </Descriptions.Item>
              <Descriptions.Item label={t("analytics.outputTokens", "Output Tokens")} span={1}>
                {formatTokens(selectedUser.output_tokens)}
              </Descriptions.Item>
            </Descriptions>

            {selectedUser.model_usage.length > 0 && (
              <div className={styles.section}>
                <h4>{t("analytics.modelUsage", "Model Usage")}</h4>
                <div className={styles.tagList}>
                  {selectedUser.model_usage.map((m) => (
                    <Tag key={m.model_name}>
                      {m.model_name}: {m.count} calls
                    </Tag>
                  ))}
                </div>
              </div>
            )}

            {selectedUser.tools_used.length > 0 && (
              <div className={styles.section}>
                <h4>{t("analytics.toolsUsed", "Tools Used")}</h4>
                <div className={styles.tagList}>
                  {selectedUser.tools_used.map((tool) => (
                    <Tag key={tool.tool_name} color={tool.error_count > 0 ? "error" : "default"}>
                      {tool.tool_name}: {tool.count} calls
                    </Tag>
                  ))}
                </div>
              </div>
            )}

            {selectedUser.skills_used.length > 0 && (
              <div className={styles.section}>
                <h4>{t("analytics.skillsUsed", "Skills Used")}</h4>
                <div className={styles.tagList}>
                  {selectedUser.skills_used.map((s) => (
                    <Tag key={s.skill_name} color="blue">
                      {s.skill_name}: {s.count} calls
                    </Tag>
                  ))}
                </div>
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
