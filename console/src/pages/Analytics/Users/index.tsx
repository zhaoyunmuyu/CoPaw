import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Table, Card, Input, Drawer, Descriptions, Spin, Empty, Tag } from "antd";
import { Search, User } from "lucide-react";
import type { ColumnsType } from "antd/es/table";
import dayjs from "dayjs";
import { request } from "../../../api";
import styles from "./index.module.less";

interface UserListItem {
  user_id: string;
  total_sessions: number;
  total_conversations: number;
  total_tokens: number;
  total_skills: number;
  last_active: string | null;
}

interface UserStats {
  user_id: string;
  model_usage: ModelUsage[];
  total_tokens: number;
  input_tokens: number;
  output_tokens: number;
  total_sessions: number;
  total_conversations: number;
  avg_duration_ms: number;
  tools_used: ToolUsage[];
  skills_used: SkillUsage[];
}

interface ModelUsage {
  model_name: string;
  count: number;
  total_tokens: number;
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
}

interface UsersResponse {
  items: UserListItem[];
  total: number;
  page: number;
  page_size: number;
}

export default function UsersPage() {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [users, setUsers] = useState<UserListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [searchQuery, setSearchQuery] = useState("");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<UserStats | null>(null);
  const [userLoading, setUserLoading] = useState(false);

  useEffect(() => {
    fetchUsers();
  }, [page, pageSize, searchQuery]);

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.append("page", page.toString());
      params.append("page_size", pageSize.toString());
      if (searchQuery) {
        params.append("user_id", searchQuery);
      }

      const data = await request<UsersResponse>(`/tracing/users?${params.toString()}`);
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
      const data = await request<UserStats>(`/tracing/users/${encodeURIComponent(userId)}`);
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
      title: t("analytics.skills", "Skills"),
      dataIndex: "total_skills",
      key: "total_skills",
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
        <Input
          placeholder={t("analytics.searchUser", "Search user...")}
          prefix={<Search size={16} />}
          value={searchQuery}
          onChange={(e) => {
            setSearchQuery(e.target.value);
            setPage(1);
          }}
          style={{ width: 250 }}
          allowClear
        />
      </div>

      <Card className={styles.tableCard}>
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
                  {selectedUser.tools_used.map((t) => (
                    <Tag key={t.tool_name} color={t.error_count > 0 ? "error" : "default"}>
                      {t.tool_name}: {t.count} calls
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
