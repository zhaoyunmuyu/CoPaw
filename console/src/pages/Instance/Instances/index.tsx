import { useEffect, useState, useCallback, useRef } from "react";
import {
  Card,
  Table,
  Button,
  Space,
  Tag,
  Progress,
  Drawer,
  Form,
  Input,
  InputNumber,
  Select,
  Modal,
  message,
} from "antd";
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import { useTranslation } from "react-i18next";
import {
  instanceApi,
  type InstanceWithUsage,
  type SourceWithStats,
} from "../../../api/modules/instance";
import { PageHeader } from "@/components/PageHeader";
import styles from "./index.module.less";

// 来源配置 - 硬编码（可扩展）
const SOURCES = [{ source_id: "rm_assistant", source_name: "RM小助" }];

// 分行配置 - 硬编码
const BRANCHES = [
  { bbk_id: "head_office", bbk_name: "总行" },
  { bbk_id: "beijing", bbk_name: "北京分行" },
  { bbk_id: "shanghai", bbk_name: "上海分行" },
  { bbk_id: "guangzhou", bbk_name: "广州分行" },
  { bbk_id: "shenzhen", bbk_name: "深圳分行" },
  { bbk_id: "chengdu", bbk_name: "成都分行" },
  { bbk_id: "hangzhou", bbk_name: "杭州分行" },
  { bbk_id: "nanjing", bbk_name: "南京分行" },
];

export default function InstancesPage() {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [instances, setInstances] = useState<InstanceWithUsage[]>([]);
  const [sources, setSources] = useState<SourceWithStats[]>([]);
  const [filterSourceId, setFilterSourceId] = useState<string | undefined>();

  // Drawer state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editingInstance, setEditingInstance] = useState<InstanceWithUsage | null>(null);
  const [form] = Form.useForm();
  const [submitting, setSubmitting] = useState(false);

  const fetchSources = useCallback(async () => {
    try {
      const data = await instanceApi.getSources();
      setSources(data.sources);
    } catch (error) {
      console.error("Failed to fetch sources:", error);
    }
  }, []);

  const fetchInstances = useCallback(async () => {
    setLoading(true);
    try {
      const data = await instanceApi.getInstances({
        source_id: filterSourceId,
      });
      const instancesWithNames = data.instances.map((inst) => ({
        ...inst,
        source_name:
          SOURCES.find((s) => s.source_id === inst.source_id)?.source_name ||
          inst.source_id,
        bbk_name:
          BRANCHES.find((b) => b.bbk_id === inst.bbk_id)?.bbk_name || inst.bbk_id,
      }));
      setInstances(instancesWithNames);
    } catch (error) {
      console.error("Failed to fetch instances:", error);
    } finally {
      setLoading(false);
    }
  }, [filterSourceId]);

  useEffect(() => {
    fetchSources();
  }, [fetchSources]);

  useEffect(() => {
    fetchInstances();
  }, [fetchInstances]);

  const handleCreate = () => {
    setEditingInstance(null);
    form.resetFields();
    form.setFieldsValue({ max_users: 100 });
    setDrawerOpen(true);
  };

  const handleEdit = (record: InstanceWithUsage) => {
    setEditingInstance(record);
    form.setFieldsValue(record);
    setDrawerOpen(true);
  };

  const handleDelete = (record: InstanceWithUsage) => {
    Modal.confirm({
      title: t("instance.confirmDelete"),
      content: t("instance.confirmDeleteInstance"),
      okText: t("common.delete"),
      okType: "danger",
      cancelText: t("common.cancel"),
      onOk: async () => {
        try {
          await instanceApi.deleteInstance(record.instance_id);
          message.success(t("instance.deleteSuccess"));
          fetchInstances();
        } catch (error: unknown) {
          message.error(
            (error as Error).message || t("instance.deleteFailed")
          );
        }
      },
    });
  };

  const handleSubmit = async (values: {
    instance_id: string;
    source_id: string;
    bbk_id?: string;
    instance_name: string;
    instance_url: string;
    max_users: number;
  }) => {
    setSubmitting(true);
    try {
      if (editingInstance) {
        await instanceApi.updateInstance(editingInstance.instance_id, {
          instance_name: values.instance_name,
          instance_url: values.instance_url,
          max_users: values.max_users,
        });
        message.success(t("instance.updateSuccess"));
      } else {
        await instanceApi.createInstance(values);
        message.success(t("instance.createSuccess"));
      }
      setDrawerOpen(false);
      fetchInstances();
    } catch (error: unknown) {
      message.error((error as Error).message || t("instance.saveFailed"));
    } finally {
      setSubmitting(false);
    }
  };

  const columns: ColumnsType<InstanceWithUsage> = [
    {
      title: t("instance.instanceId"),
      dataIndex: "instance_id",
      key: "instance_id",
      width: 120,
    },
    {
      title: t("instance.instanceName"),
      dataIndex: "instance_name",
      key: "instance_name",
    },
    {
      title: t("instance.source"),
      dataIndex: "source_name",
      key: "source_name",
      width: 100,
    },
    {
      title: t("instance.branch"),
      dataIndex: "bbk_name",
      key: "bbk_name",
      width: 100,
      render: (v) => v || "-",
    },
    {
      title: t("instance.userUsage"),
      key: "usage",
      width: 150,
      render: (_, record) => {
        const percent = record.usage_percent;
        let status: "success" | "normal" | "exception" = "success";
        if (percent >= 100) status = "exception";
        else if (percent >= 80) status = "normal";
        return (
          <Progress
            percent={Math.min(percent, 100)}
            status={status}
            format={() => `${record.current_users}/${record.max_users}`}
            size="small"
          />
        );
      },
    },
    {
      title: t("instance.status"),
      dataIndex: "status",
      key: "status",
      width: 80,
      render: (v) => (
        <Tag color={v === "active" ? "green" : "default"}>
          {v === "active" ? t("instance.active") : t("instance.inactive")}
        </Tag>
      ),
    },
    {
      title: t("instance.warning"),
      key: "warning",
      width: 80,
      render: (_, record) => {
        if (record.warning_level === "critical")
          return <Tag color="red">{t("instance.critical")}</Tag>;
        if (record.warning_level === "warning")
          return <Tag color="orange">{t("instance.warning")}</Tag>;
        return <Tag color="green">{t("instance.normal")}</Tag>;
      },
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
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
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
    <div className={styles.instancesPage}>
      <PageHeader
        items={[{ title: t("nav.instance") }, { title: t("instance.instances") }]}
        extra={
          <Space>
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
            <Button icon={<ReloadOutlined spin={loading} />} onClick={fetchInstances}>
              {t("common.refresh")}
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
              {t("instance.addInstance")}
            </Button>
          </Space>
        }
      />

      <Card className={styles.tableCard}>
        <Table
          columns={columns}
          dataSource={instances}
          rowKey="instance_id"
          loading={loading}
          scroll={{ x: 1000 }}
        />
      </Card>

      <Drawer
        title={editingInstance ? t("instance.editInstance") : t("instance.addInstance")}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={500}
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item
            name="instance_id"
            label={t("instance.instanceId")}
            rules={[{ required: true, message: t("instance.required") }]}
          >
            <Input disabled={!!editingInstance} />
          </Form.Item>
          <Form.Item
            name="instance_name"
            label={t("instance.instanceName")}
            rules={[{ required: true, message: t("instance.required") }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="instance_url"
            label={t("instance.instanceUrl")}
            rules={[{ required: true, message: t("instance.required") }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="source_id"
            label={t("instance.belongToSource")}
            rules={[{ required: true, message: t("instance.required") }]}
          >
            <Select disabled={!!editingInstance}>
              {SOURCES.map((s) => (
                <Select.Option key={s.source_id} value={s.source_id}>
                  {s.source_name}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="bbk_id" label={t("instance.belongToBranch")}>
            <Select allowClear disabled={!!editingInstance}>
              {BRANCHES.map((b) => (
                <Select.Option key={b.bbk_id} value={b.bbk_id}>
                  {b.bbk_name}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item
            name="max_users"
            label={t("instance.userThreshold")}
            rules={[{ required: true, message: t("instance.required") }]}
          >
            <InputNumber min={1} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={submitting}>
                {t("common.save")}
              </Button>
              <Button onClick={() => setDrawerOpen(false)}>
                {t("common.cancel")}
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Drawer>
    </div>
  );
}
