import { useState, useEffect, useCallback } from "react";
import { Button, Card, Table, Modal, Input } from "antd";
import { Form } from "@agentscope-ai/design";
import { PageHeader } from "@/components/PageHeader";
import { useGreeting } from "./components/hooks";
import { createColumns } from "./components/columns";
import { GreetingDrawer } from "./components/GreetingDrawer";
import type { GreetingConfig } from "@/api/types/greeting";
import styles from "./index.module.less";

function GreetingPage() {
  const { configs, loading, total, loadConfigs, createConfig, updateConfig, deleteConfig } =
    useGreeting();

  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editingConfig, setEditingConfig] = useState<GreetingConfig | null>(null);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm<GreetingConfig>();

  // Filters
  const [sourceIdFilter, setSourceIdFilter] = useState("");
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20 });

  // Load data on mount and when filters change
  useEffect(() => {
    loadConfigs({
      source_id: sourceIdFilter || undefined,
      page: pagination.current,
      page_size: pagination.pageSize,
    });
  }, [loadConfigs, sourceIdFilter, pagination.current, pagination.pageSize]);

  const handleCreate = () => {
    setEditingConfig(null);
    form.resetFields();
    setDrawerOpen(true);
  };

  const handleEdit = (config: GreetingConfig) => {
    setEditingConfig(config);
    form.setFieldsValue(config);
    setDrawerOpen(true);
  };

  const handleDelete = (id: number) => {
    Modal.confirm({
      title: "确认删除",
      content: "确定要删除此配置吗？",
      okText: "删除",
      okType: "danger",
      cancelText: "取消",
      onOk: async () => {
        await deleteConfig(id);
        loadConfigs({
          source_id: sourceIdFilter || undefined,
          page: pagination.current,
          page_size: pagination.pageSize,
        });
      },
    });
  };

  const handleDrawerClose = () => {
    setDrawerOpen(false);
    setEditingConfig(null);
  };

  const handleSubmit = async (values: GreetingConfig) => {
    setSaving(true);
    try {
      if (editingConfig) {
        await updateConfig(editingConfig.id, values);
      } else {
        await createConfig(values);
      }
      setDrawerOpen(false);
      loadConfigs({
        source_id: sourceIdFilter || undefined,
        page: pagination.current,
        page_size: pagination.pageSize,
      });
    } catch (error) {
      // Error handled in hooks
    } finally {
      setSaving(false);
    }
  };

  const columns = createColumns({
    onEdit: handleEdit,
    onDelete: handleDelete,
  });

  const handleTableChange = (pag: { current?: number; pageSize?: number }) => {
    setPagination({
      current: pag.current || 1,
      pageSize: pag.pageSize || 20,
    });
  };

  return (
    <div className={styles.greetingPage}>
      <PageHeader
        items={[{ title: "控制" }, { title: "引导文案管理" }]}
        extra={
          <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
            <Input.Search
              placeholder="搜索 Source ID"
              allowClear
              onSearch={(val) => {
                setSourceIdFilter(val);
                setPagination({ ...pagination, current: 1 });
              }}
              style={{ width: 200 }}
            />
            <Button type="primary" onClick={handleCreate}>
              + 新建配置
            </Button>
          </div>
        }
      />

      <Card className={styles.tableCard} bodyStyle={{ padding: 0 }}>
        <Table
          columns={columns}
          dataSource={configs}
          loading={loading}
          rowKey="id"
          pagination={{
            current: pagination.current,
            pageSize: pagination.pageSize,
            total,
            showSizeChanger: true,
            showTotal: (t) => `共 ${t} 条`,
          }}
          onChange={handleTableChange}
        />
      </Card>

      <GreetingDrawer
        open={drawerOpen}
        editingConfig={editingConfig}
        form={form}
        saving={saving}
        onClose={handleDrawerClose}
        onSubmit={handleSubmit}
      />
    </div>
  );
}

export default GreetingPage;
