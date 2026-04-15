import { useEffect, useState, useCallback, useRef } from "react";
import {
  Card,
  Table,
  Button,
  Space,
  Tag,
  Drawer,
  Form,
  Input,
  Select,
  Modal,
  message,
} from "antd";
import {
  PlusOutlined,
  SwapOutlined,
  DeleteOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import { useTranslation } from "react-i18next";
import {
  instanceApi,
  type UserAllocation,
  type InstanceWithUsage,
  type SourceWithStats,
  type AllocateUserRequest,
} from "../../../api/modules/instance";
import { PageHeader } from "@/components/PageHeader";
import styles from "./index.module.less";

// 来源配置 - 硬编码（可扩展）
const SOURCES = [{ source_id: "rm_assistant", source_name: "RM小助" }];

export default function AllocationsPage() {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [allocations, setAllocations] = useState<UserAllocation[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [sources, setSources] = useState<SourceWithStats[]>([]);
  const [instances, setInstances] = useState<InstanceWithUsage[]>([]);

  // Filters
  const [filterUserId, setFilterUserId] = useState("");
  const [filterSourceId, setFilterSourceId] = useState<string | undefined>();

  // Add allocation drawer
  const [addDrawerOpen, setAddDrawerOpen] = useState(false);
  const [addForm] = Form.useForm();
  const [submitting, setSubmitting] = useState(false);

  // Migrate drawer
  const [migrateDrawerOpen, setMigrateDrawerOpen] = useState(false);
  const [migratingAllocation, setMigratingAllocation] =
    useState<UserAllocation | null>(null);
  const [migrateForm] = Form.useForm();
  const [migrateSubmitting, setMigrateSubmitting] = useState(false);

  const filtersRef = useRef({
    user_id: "",
    source_id: undefined as string | undefined,
  });

  const fetchSources = useCallback(async () => {
    try {
      const data = await instanceApi.getSources();
      setSources(data.sources);
    } catch (error) {
      console.error("Failed to fetch sources:", error);
    }
  }, []);

  const fetchInstances = useCallback(async () => {
    try {
      const data = await instanceApi.getInstances();
      setInstances(data.instances);
    } catch (error) {
      console.error("Failed to fetch instances:", error);
    }
  }, []);

  const fetchAllocations = useCallback(async () => {
    setLoading(true);
    try {
      const data = await instanceApi.getAllocations({
        user_id: filterUserId || undefined,
        source_id: filterSourceId,
        page,
        page_size: pageSize,
      });
      const allocationsWithNames = data.allocations.map((alloc) => ({
        ...alloc,
        source_name:
          SOURCES.find((s) => s.source_id === alloc.source_id)?.source_name ||
          alloc.source_id,
        instance_name:
          instances.find((i) => i.instance_id === alloc.instance_id)
            ?.instance_name || alloc.instance_id,
      }));
      setAllocations(allocationsWithNames);
      setTotal(data.total);
    } catch (error) {
      console.error("Failed to fetch allocations:", error);
    } finally {
      setLoading(false);
    }
  }, [filterUserId, filterSourceId, page, pageSize, instances]);

  useEffect(() => {
    fetchSources();
    fetchInstances();
  }, [fetchSources, fetchInstances]);

  useEffect(() => {
    const filtersChanged =
      filtersRef.current.user_id !== filterUserId ||
      filtersRef.current.source_id !== filterSourceId;

    filtersRef.current = { user_id: filterUserId, source_id: filterSourceId };

    if (filtersChanged && page !== 1) {
      setPage(1);
      return;
    }

    if (instances.length > 0) {
      fetchAllocations();
    }
  }, [
    filterUserId,
    filterSourceId,
    page,
    pageSize,
    instances,
    fetchAllocations,
  ]);

  const handleCreate = () => {
    addForm.resetFields();
    setAddDrawerOpen(true);
  };

  const handleSaveAllocation = async (values: AllocateUserRequest) => {
    setSubmitting(true);
    try {
      const result = await instanceApi.allocateUser(values);
      if (result.success) {
        message.success(
          `${t("instance.allocateSuccess")}: ${result.instance_url}`,
        );
        setAddDrawerOpen(false);
        fetchAllocations();
        fetchInstances();
      } else {
        message.warning(result.message || t("instance.allocateFailed"));
      }
    } catch (error: unknown) {
      message.error((error as Error).message || t("instance.allocateFailed"));
    } finally {
      setSubmitting(false);
    }
  };

  const handleMigrate = (record: UserAllocation) => {
    setMigratingAllocation(record);
    migrateForm.resetFields();
    migrateForm.setFieldsValue({
      user_id: record.user_id,
      source_id: record.source_id,
    });
    setMigrateDrawerOpen(true);
  };

  const handleSaveMigrate = async (values: { target_instance_id: string }) => {
    if (!migratingAllocation) return;
    setMigrateSubmitting(true);
    try {
      const result = await instanceApi.migrateUser({
        user_id: migratingAllocation.user_id,
        source_id: migratingAllocation.source_id,
        target_instance_id: values.target_instance_id,
      });
      if (result.success) {
        message.success(t("instance.migrateSuccess"));
        setMigrateDrawerOpen(false);
        fetchAllocations();
        fetchInstances();
      } else {
        message.warning(result.message || t("instance.migrateFailed"));
      }
    } catch (error: unknown) {
      message.error((error as Error).message || t("instance.migrateFailed"));
    } finally {
      setMigrateSubmitting(false);
    }
  };

  const handleDelete = (record: UserAllocation) => {
    Modal.confirm({
      title: t("instance.confirmDelete"),
      content: t("instance.confirmDeleteAllocation", {
        userId: record.user_id,
      }),
      okText: t("common.delete"),
      okType: "danger",
      cancelText: t("common.cancel"),
      onOk: async () => {
        try {
          await instanceApi.deleteAllocation(record.user_id, record.source_id);
          message.success(t("instance.deleteSuccess"));
          fetchAllocations();
          fetchInstances();
        } catch (error: unknown) {
          message.error((error as Error).message || t("instance.deleteFailed"));
        }
      },
    });
  };

  const columns: ColumnsType<UserAllocation> = [
    {
      title: t("instance.userId"),
      dataIndex: "user_id",
      key: "user_id",
      width: 160,
    },
    {
      title: t("instance.source"),
      dataIndex: "source_name",
      key: "source_name",
      width: 100,
    },
    {
      title: t("instance.instanceName"),
      dataIndex: "instance_name",
      key: "instance_name",
    },
    {
      title: t("instance.instanceUrl"),
      dataIndex: "instance_url",
      key: "instance_url",
      ellipsis: true,
      render: (v) => v || "-",
    },
    {
      title: t("instance.status"),
      dataIndex: "status",
      key: "status",
      width: 80,
      render: (v) => (
        <Tag color={v === "active" ? "green" : "blue"}>
          {v === "active" ? t("instance.active") : t("instance.migrated")}
        </Tag>
      ),
    },
    {
      title: t("instance.allocatedAt"),
      dataIndex: "allocated_at",
      key: "allocated_at",
      width: 160,
      render: (v) => (v ? new Date(v).toLocaleString() : "-"),
    },
    {
      title: t("common.actions"),
      key: "action",
      width: 100,
      render: (_, record) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<SwapOutlined />}
            onClick={() => handleMigrate(record)}
          />
          <Button
            type="link"
            size="small"
            danger
            icon={<DeleteOutlined />}
            onClick={() => handleDelete(record)}
          />
        </Space>
      ),
    },
  ];

  return (
    <div className={styles.allocationsPage}>
      <PageHeader
        items={[
          { title: t("nav.instance") },
          { title: t("instance.allocations") },
        ]}
        extra={
          <Space>
            <Input
              placeholder={t("instance.searchUserId")}
              style={{ width: 200 }}
              value={filterUserId}
              onChange={(e) => setFilterUserId(e.target.value)}
              allowClear
            />
            <Select
              allowClear
              placeholder={t("instance.filterSource")}
              style={{ width: 150 }}
              value={filterSourceId}
              onChange={(v) => setFilterSourceId(v)}
            >
              {sources.map((s) => (
                <Select.Option key={s.source_id} value={s.source_id}>
                  {s.source_name}
                </Select.Option>
              ))}
            </Select>
            <Button
              icon={<ReloadOutlined spin={loading} />}
              onClick={fetchAllocations}
            >
              {t("common.refresh")}
            </Button>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={handleCreate}
            >
              {t("instance.addAllocation")}
            </Button>
          </Space>
        }
      />

      <Card className={styles.tableCard}>
        <Table
          columns={columns}
          dataSource={allocations}
          rowKey="id"
          loading={loading}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (totalItems) => t("common.total", { count: totalItems }),
            onChange: (p, ps) => {
              setPage(p);
              setPageSize(ps);
            },
          }}
        />
      </Card>

      {/* Add Allocation Drawer */}
      <Drawer
        title={t("instance.addAllocation")}
        open={addDrawerOpen}
        onClose={() => setAddDrawerOpen(false)}
        width={400}
      >
        <Form form={addForm} layout="vertical" onFinish={handleSaveAllocation}>
          <Form.Item
            name="user_id"
            label={t("instance.userId")}
            rules={[{ required: true, message: t("instance.required") }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="source_id"
            label={t("instance.belongToSource")}
            rules={[{ required: true, message: t("instance.required") }]}
          >
            <Select>
              {SOURCES.map((s) => (
                <Select.Option key={s.source_id} value={s.source_id}>
                  {s.source_name}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item
            name="instance_id"
            label={t("instance.specifyInstance")}
            extra={t("instance.autoAllocateHint")}
          >
            <Select allowClear>
              {instances.map((i) => (
                <Select.Option key={i.instance_id} value={i.instance_id}>
                  {i.instance_name} ({i.current_users}/{i.max_users})
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={submitting}>
                {t("instance.addAllocation")}
              </Button>
              <Button onClick={() => setAddDrawerOpen(false)}>
                {t("common.cancel")}
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Drawer>

      {/* Migrate Drawer */}
      <Drawer
        title={t("instance.migrate")}
        open={migrateDrawerOpen}
        onClose={() => setMigrateDrawerOpen(false)}
        width={400}
      >
        <Form form={migrateForm} layout="vertical" onFinish={handleSaveMigrate}>
          <Form.Item label={t("instance.userId")}>
            <Input value={migratingAllocation?.user_id} disabled />
          </Form.Item>
          <Form.Item
            name="target_instance_id"
            label={t("instance.targetInstance")}
            rules={[{ required: true, message: t("instance.required") }]}
          >
            <Select>
              {instances
                .filter((i) => i.source_id === migratingAllocation?.source_id)
                .map((i) => (
                  <Select.Option key={i.instance_id} value={i.instance_id}>
                    {i.instance_name} ({i.current_users}/{i.max_users})
                  </Select.Option>
                ))}
            </Select>
          </Form.Item>
          <Form.Item>
            <Space>
              <Button
                type="primary"
                htmlType="submit"
                loading={migrateSubmitting}
              >
                {t("instance.migrate")}
              </Button>
              <Button onClick={() => setMigrateDrawerOpen(false)}>
                {t("common.cancel")}
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Drawer>
    </div>
  );
}
