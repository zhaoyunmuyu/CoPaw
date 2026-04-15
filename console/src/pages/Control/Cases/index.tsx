import { useState, useEffect, useRef } from "react";
import { Button, Card, Table, Modal, Tabs, Checkbox, Input } from "antd";
import { Form } from "@agentscope-ai/design";
import { PageHeader } from "@/components/PageHeader";
import { useCases } from "./components/hooks";
import { createColumns } from "./components/columns";
import { CaseDrawer } from "./components/CaseDrawer";
import type { Case } from "@/api/types/cases";
import styles from "./index.module.less";

function CasesPage() {
  const {
    cases,
    loading,
    userMapping,
    loadCases,
    loadUserMapping,
    createCase,
    updateCase,
    deleteCase,
    updateUserMapping,
  } = useCases();

  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editingCase, setEditingCase] = useState<Case | null>(null);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm<Case>();

  // Load data on mount
  useEffect(() => {
    loadCases();
    loadUserMapping();
  }, [loadCases, loadUserMapping]);

  const handleCreate = () => {
    setEditingCase(null);
    form.resetFields();
    setDrawerOpen(true);
  };

  const handleEdit = (caseItem: Case) => {
    setEditingCase(caseItem);
    form.setFieldsValue(caseItem);
    setDrawerOpen(true);
  };

  const handleDelete = (caseId: string) => {
    Modal.confirm({
      title: "确认删除",
      content: `确定要删除案例 "${caseId}" 吗？`,
      okText: "删除",
      okType: "danger",
      cancelText: "取消",
      onOk: async () => {
        await deleteCase(caseId);
      },
    });
  };

  const handleDrawerClose = () => {
    setDrawerOpen(false);
    setEditingCase(null);
  };

  const handleSubmit = async (values: Case) => {
    setSaving(true);
    try {
      if (editingCase) {
        await updateCase(editingCase.id, values);
      } else {
        await createCase(values);
      }
      setDrawerOpen(false);
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

  // User assignment tab state
  const [newUserId, setNewUserId] = useState("");
  const [newUserCases, setNewUserCases] = useState<string[]>([]);
  const userMappingRef = useRef<Record<string, string[]>>(userMapping);

  // Sync ref with state
  useEffect(() => {
    userMappingRef.current = userMapping;
  }, [userMapping]);

  const handleUserCaseChange = (userId: string, caseIds: string[]) => {
    const newMapping = { ...userMappingRef.current, [userId]: caseIds };
    updateUserMapping(newMapping);
  };

  const handleAddUser = () => {
    if (!newUserId.trim()) return;
    if (userMappingRef.current[newUserId]) return;

    const newMapping = {
      ...userMappingRef.current,
      [newUserId]: newUserCases,
    };
    updateUserMapping(newMapping);
    setNewUserId("");
    setNewUserCases([]);
  };

  const handleRemoveUser = (userId: string) => {
    if (userId === "default") {
      Modal.warning({
        title: "无法删除",
        content: "default 映射不能删除",
      });
      return;
    }

    Modal.confirm({
      title: "确认删除",
      content: `确定要删除用户 "${userId}" 的案例映射吗？`,
      okText: "删除",
      okType: "danger",
      cancelText: "取消",
      onOk: () => {
        const newMapping = { ...userMappingRef.current };
        delete newMapping[userId];
        updateUserMapping(newMapping);
      },
    });
  };

  // Tab items
  const tabItems = [
    {
      key: "cases",
      label: "案例定义",
      children: (
        <Card className={styles.tableCard} bodyStyle={{ padding: 0 }}>
          <Table
            columns={columns}
            dataSource={cases}
            loading={loading}
            rowKey="id"
            pagination={{ pageSize: 10 }}
          />
        </Card>
      ),
    },
    {
      key: "user-mapping",
      label: "用户分配",
      children: (
        <Card className={styles.tableCard}>
          <div style={{ marginBottom: 16 }}>
            <Input
              placeholder="输入 userId"
              value={newUserId}
              onChange={(e) => setNewUserId(e.target.value)}
              style={{ width: 200, marginRight: 8 }}
            />
            <Checkbox.Group
              options={cases.map((c) => ({
                label: c.label.slice(0, 30) + (c.label.length > 30 ? "..." : ""),
                value: c.id,
              }))}
              value={newUserCases}
              onChange={(vals) => setNewUserCases(vals as string[])}
              style={{ marginBottom: 8 }}
            />
            <Button type="primary" onClick={handleAddUser}>
              添加用户
            </Button>
          </div>

          <Table
            dataSource={Object.entries(userMapping).map(([userId, caseIds]) => ({
              userId,
              caseIds,
            }))}
            rowKey="userId"
            pagination={false}
            columns={[
              {
                title: "userId",
                dataIndex: "userId",
                key: "userId",
                width: 150,
              },
              {
                title: "可见案例",
                dataIndex: "caseIds",
                key: "caseIds",
                render: (caseIds: string[], record) => (
                  <Checkbox.Group
                    options={cases.map((c) => ({
                      label: c.id,
                      value: c.id,
                    }))}
                    value={caseIds}
                    onChange={(vals) =>
                      handleUserCaseChange(record.userId, vals as string[])
                    }
                  />
                ),
              },
              {
                title: "操作",
                key: "action",
                width: 80,
                render: (_, record) => (
                  <a
                    onClick={() => handleRemoveUser(record.userId)}
                    style={{ color: "#ff4d4f" }}
                  >
                    删除
                  </a>
                ),
              },
            ]}
          />
        </Card>
      ),
    },
  ];

  return (
    <div className={styles.casesPage}>
      <PageHeader
        items={[{ title: "控制" }, { title: "案例管理" }]}
        extra={
          <Button type="primary" onClick={handleCreate}>
            + 新建案例
          </Button>
        }
      />

      <Tabs items={tabItems} />

      <CaseDrawer
        open={drawerOpen}
        editingCase={editingCase}
        form={form}
        saving={saving}
        onClose={handleDrawerClose}
        onSubmit={handleSubmit}
      />
    </div>
  );
}

export default CasesPage;