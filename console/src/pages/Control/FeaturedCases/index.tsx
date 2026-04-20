import { useState, useEffect } from "react";
import { Button, Card, Table, Modal, Tabs, Input } from "antd";
import { Form } from "@agentscope-ai/design";
import { PageHeader } from "@/components/PageHeader";
import { useFeaturedCases } from "./components/hooks";
import { createCaseColumns, createConfigColumns } from "./components/columns";
import { CaseDrawer } from "./components/CaseDrawer";
import { ConfigDrawer } from "./components/ConfigDrawer";
import type { FeaturedCase, CaseConfigListItem } from "@/api/types/featuredCases";
import styles from "./index.module.less";

function FeaturedCasesPage() {
  const {
    cases,
    casesLoading,
    casesTotal,
    configs,
    configsLoading,
    configsTotal,
    loadCases,
    loadConfigs,
    createCase,
    updateCase,
    deleteCase,
    upsertConfig,
    deleteConfig,
    getConfigDetail,
  } = useFeaturedCases();

  // Case drawer state
  const [caseDrawerOpen, setCaseDrawerOpen] = useState(false);
  const [editingCase, setEditingCase] = useState<FeaturedCase | null>(null);
  const [caseSaving, setCaseSaving] = useState(false);
  const [caseForm] = Form.useForm<FeaturedCase>();

  // Config drawer state
  const [configDrawerOpen, setConfigDrawerOpen] = useState(false);
  const [editingSourceId, setEditingSourceId] = useState<string | null>(null);
  const [editingBbkId, setEditingBbkId] = useState<string | null>(null);

  // Pagination
  const [casesPagination, setCasesPagination] = useState({
    current: 1,
    pageSize: 20,
  });
  const [configsPagination, setConfigsPagination] = useState({
    current: 1,
    pageSize: 20,
  });

  // Filters
  const [sourceIdFilter, setSourceIdFilter] = useState("");

  // Load data on mount
  useEffect(() => {
    loadCases({
      page: casesPagination.current,
      page_size: casesPagination.pageSize,
    });
    loadConfigs({
      source_id: sourceIdFilter || undefined,
      page: configsPagination.current,
      page_size: configsPagination.pageSize,
    });
  }, [
    loadCases,
    loadConfigs,
    casesPagination.current,
    casesPagination.pageSize,
    configsPagination.current,
    configsPagination.pageSize,
    sourceIdFilter,
  ]);

  // ==================== Case handlers ====================

  const handleCreateCase = () => {
    setEditingCase(null);
    caseForm.resetFields();
    setCaseDrawerOpen(true);
  };

  const handleEditCase = (caseItem: FeaturedCase) => {
    setEditingCase(caseItem);
    caseForm.setFieldsValue(caseItem);
    setCaseDrawerOpen(true);
  };

  const handleDeleteCase = (caseId: string) => {
    Modal.confirm({
      title: "确认删除",
      content: `确定要删除案例 "${caseId}" 吗？`,
      okText: "删除",
      okType: "danger",
      cancelText: "取消",
      onOk: async () => {
        await deleteCase(caseId);
        loadCases({
          page: casesPagination.current,
          page_size: casesPagination.pageSize,
        });
      },
    });
  };

  const handleCaseDrawerClose = () => {
    setCaseDrawerOpen(false);
    setEditingCase(null);
  };

  const handleCaseSubmit = async (values: FeaturedCase) => {
    setCaseSaving(true);
    try {
      if (editingCase) {
        await updateCase(editingCase.case_id, values);
      } else {
        await createCase(values);
      }
      setCaseDrawerOpen(false);
      loadCases({
        page: casesPagination.current,
        page_size: casesPagination.pageSize,
      });
    } catch (error) {
      // Error handled in hooks
    } finally {
      setCaseSaving(false);
    }
  };

  // ==================== Config handlers ====================

  const handleCreateConfig = () => {
    setEditingSourceId(null);
    setEditingBbkId(null);
    setConfigDrawerOpen(true);
  };

  const handleEditConfig = (config: CaseConfigListItem) => {
    setEditingSourceId(config.source_id);
    setEditingBbkId(config.bbk_id);
    setConfigDrawerOpen(true);
  };

  const handleDeleteConfig = (config: CaseConfigListItem) => {
    Modal.confirm({
      title: "确认删除",
      content: `确定要删除维度配置 "${config.source_id}${config.bbk_id ? `/${config.bbk_id}` : ""}" 吗？`,
      okText: "删除",
      okType: "danger",
      cancelText: "取消",
      onOk: async () => {
        await deleteConfig(config.source_id, config.bbk_id);
        loadConfigs({
          source_id: sourceIdFilter || undefined,
          page: configsPagination.current,
          page_size: configsPagination.pageSize,
        });
      },
    });
  };

  const handleConfigDrawerClose = () => {
    setConfigDrawerOpen(false);
    setEditingSourceId(null);
    setEditingBbkId(null);
  };

  const handleConfigSuccess = () => {
    loadConfigs({
      source_id: sourceIdFilter || undefined,
      page: configsPagination.current,
      page_size: configsPagination.pageSize,
    });
  };

  // ==================== Table change handlers ====================

  const handleCasesTableChange = (pag: { current?: number; pageSize?: number }) => {
    setCasesPagination({
      current: pag.current || 1,
      pageSize: pag.pageSize || 20,
    });
  };

  const handleConfigsTableChange = (pag: { current?: number; pageSize?: number }) => {
    setConfigsPagination({
      current: pag.current || 1,
      pageSize: pag.pageSize || 20,
    });
  };

  // ==================== Columns ====================

  const caseColumns = createCaseColumns({
    onEdit: handleEditCase,
    onDelete: handleDeleteCase,
  });

  const configColumns = createConfigColumns({
    onConfig: handleEditConfig,
    onDelete: handleDeleteConfig,
  });

  // ==================== Tabs ====================

  const tabItems = [
    {
      key: "cases",
      label: "案例定义",
      children: (
        <Card className={styles.tableCard} bodyStyle={{ padding: 0 }}>
          <Table
            columns={caseColumns}
            dataSource={cases}
            loading={casesLoading}
            rowKey="case_id"
            pagination={{
              current: casesPagination.current,
              pageSize: casesPagination.pageSize,
              total: casesTotal,
              showSizeChanger: true,
              showTotal: (t) => `共 ${t} 条`,
            }}
            onChange={handleCasesTableChange}
          />
        </Card>
      ),
    },
    {
      key: "configs",
      label: "维度配置",
      children: (
        <Card className={styles.tableCard}>
          <div style={{ marginBottom: 16 }}>
            <Input.Search
              placeholder="搜索 Source ID"
              allowClear
              onSearch={(val) => {
                setSourceIdFilter(val);
                setConfigsPagination({ ...configsPagination, current: 1 });
              }}
              style={{ width: 200, marginRight: 16 }}
            />
            <Button type="primary" onClick={handleCreateConfig}>
              + 新建配置
            </Button>
          </div>

          <Table
            columns={configColumns}
            dataSource={configs}
            loading={configsLoading}
            rowKey={(r) => `${r.source_id}-${r.bbk_id || "null"}`}
            pagination={{
              current: configsPagination.current,
              pageSize: configsPagination.pageSize,
              total: configsTotal,
              showSizeChanger: true,
              showTotal: (t) => `共 ${t} 条`,
            }}
            onChange={handleConfigsTableChange}
          />
        </Card>
      ),
    },
  ];

  return (
    <div className={styles.featuredCasesPage}>
      <PageHeader
        items={[{ title: "控制" }, { title: "精选案例管理" }]}
        extra={
          <Button type="primary" onClick={handleCreateCase}>
            + 新建案例
          </Button>
        }
      />

      <Tabs items={tabItems} />

      <CaseDrawer
        open={caseDrawerOpen}
        editingCase={editingCase}
        form={caseForm}
        saving={caseSaving}
        onClose={handleCaseDrawerClose}
        onSubmit={handleCaseSubmit}
      />

      <ConfigDrawer
        open={configDrawerOpen}
        editingSourceId={editingSourceId}
        editingBbkId={editingBbkId}
        onClose={handleConfigDrawerClose}
        onSuccess={handleConfigSuccess}
        allCases={cases}
        upsertConfig={upsertConfig}
        getConfigDetail={getConfigDetail}
      />
    </div>
  );
}

export default FeaturedCasesPage;
