import { useEffect, useState, useCallback } from "react";
import {
  Card,
  Table,
  Button,
  Select,
  Space,
  Tag,
  Typography,
  Tooltip,
} from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import { instanceApi, type OperationLog } from "../../../api/modules/instance";
import { PageHeader } from "@/components/PageHeader";
import styles from "./index.module.less";

const { Text } = Typography;

export default function OperationLogsPage() {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [logs, setLogs] = useState<OperationLog[]>([]);
  const [total, setTotal] = useState(0);

  // Pagination
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  // Filters
  const [filterAction, setFilterAction] = useState("");
  const [filterTargetType, setFilterTargetType] = useState("");
  const [filterTargetId, setFilterTargetId] = useState("");

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const result = await instanceApi.getLogs({
        action: filterAction || undefined,
        target_type: filterTargetType || undefined,
        target_id: filterTargetId || undefined,
        page,
        page_size: pageSize,
      });
      setLogs(result.logs);
      setTotal(result.total);
    } catch (error) {
      console.error("Failed to fetch logs:", error);
    } finally {
      setLoading(false);
    }
  }, [filterAction, filterTargetType, filterTargetId, page, pageSize]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const getActionColor = (action: string) => {
    if (action.includes("create")) return "green";
    if (action.includes("update")) return "blue";
    if (action.includes("delete")) return "red";
    if (action.includes("migrate")) return "orange";
    if (action.includes("allocate")) return "cyan";
    return "default";
  };

  const getActionLabel = (action: string) => {
    const labels: Record<string, string> = {
      create_instance: t("instance.actionCreateInstance"),
      update_instance: t("instance.actionUpdateInstance"),
      delete_instance: t("instance.actionDeleteInstance"),
      allocate: t("instance.actionAllocate"),
      migrate: t("instance.actionMigrate"),
      delete_allocation: t("instance.actionDeleteAllocation"),
    };
    return labels[action] || action;
  };

  const columns = [
    {
      title: t("instance.action"),
      dataIndex: "action",
      key: "action",
      width: 150,
      render: (action: string) => (
        <Tag color={getActionColor(action)}>{getActionLabel(action)}</Tag>
      ),
    },
    {
      title: t("instance.targetType"),
      dataIndex: "target_type",
      key: "target_type",
      width: 100,
      render: (type: string) => t(`instance.targetType_${type}`),
    },
    {
      title: t("instance.targetId"),
      dataIndex: "target_id",
      key: "target_id",
      width: 160,
      ellipsis: true,
    },
    {
      title: t("instance.oldValue"),
      dataIndex: "old_value",
      key: "old_value",
      width: 200,
      ellipsis: true,
      render: (value: unknown) =>
        value ? (
          <Tooltip title={JSON.stringify(value, null, 2)}>
            <Text code ellipsis style={{ maxWidth: 180 }}>
              {JSON.stringify(value)}
            </Text>
          </Tooltip>
        ) : (
          "-"
        ),
    },
    {
      title: t("instance.newValue"),
      dataIndex: "new_value",
      key: "new_value",
      width: 200,
      ellipsis: true,
      render: (value: unknown) =>
        value ? (
          <Tooltip title={JSON.stringify(value, null, 2)}>
            <Text code ellipsis style={{ maxWidth: 180 }}>
              {JSON.stringify(value)}
            </Text>
          </Tooltip>
        ) : (
          "-"
        ),
    },
    {
      title: t("instance.operator"),
      dataIndex: "operator",
      key: "operator",
      width: 120,
      render: (op: string) => op || "-",
    },
    {
      title: t("instance.createdAt"),
      dataIndex: "created_at",
      key: "created_at",
      width: 180,
      render: (date: string) => (date ? new Date(date).toLocaleString() : "-"),
    },
  ];

  return (
    <div className={styles.logsPage}>
      <PageHeader
        items={[
          { title: t("nav.instance") },
          { title: t("nav.instanceOperationLogs") },
        ]}
        extra={
          <Space>
            <Select
              allowClear
              placeholder={t("instance.filterByAction")}
              style={{ width: 180 }}
              value={filterAction || undefined}
              onChange={(v) => {
                setFilterAction(v || "");
                setPage(1);
              }}
              options={[
                {
                  label: t("instance.actionCreateInstance"),
                  value: "create_instance",
                },
                {
                  label: t("instance.actionUpdateInstance"),
                  value: "update_instance",
                },
                {
                  label: t("instance.actionDeleteInstance"),
                  value: "delete_instance",
                },
                { label: t("instance.actionAllocate"), value: "allocate" },
                { label: t("instance.actionMigrate"), value: "migrate" },
                {
                  label: t("instance.actionDeleteAllocation"),
                  value: "delete_allocation",
                },
              ]}
            />
            <Select
              allowClear
              placeholder={t("instance.filterByTargetType")}
              style={{ width: 120 }}
              value={filterTargetType || undefined}
              onChange={(v) => {
                setFilterTargetType(v || "");
                setPage(1);
              }}
              options={[
                { label: t("instance.targetType_source"), value: "source" },
                { label: t("instance.targetType_instance"), value: "instance" },
                { label: t("instance.targetType_user"), value: "user" },
              ]}
            />
            <Select
              allowClear
              showSearch
              placeholder={t("instance.searchTargetId")}
              style={{ width: 180 }}
              value={filterTargetId || undefined}
              onChange={(v) => {
                setFilterTargetId(v || "");
                setPage(1);
              }}
              options={[]}
              onSearch={(v) => setFilterTargetId(v)}
            />
            <Button
              icon={<ReloadOutlined spin={loading} />}
              onClick={fetchData}
              loading={loading}
            >
              {t("common.refresh")}
            </Button>
          </Space>
        }
      />

      <Card className={styles.tableCard}>
        <Table
          columns={columns}
          dataSource={logs}
          rowKey="id"
          loading={loading}
          scroll={{ x: 1300 }}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total) => t("common.total", { count: total }),
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
