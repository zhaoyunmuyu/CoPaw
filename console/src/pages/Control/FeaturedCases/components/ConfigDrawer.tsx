import { useState, useEffect } from "react";
import { Drawer, Form, Input, Button, Checkbox, Spin, message } from "antd";
import type { FeaturedCase } from "@/api/types/featuredCases";

interface ConfigDrawerProps {
  open: boolean;
  editingSourceId: string | null;
  editingBbkId: string | null;
  onClose: () => void;
  onSuccess: () => void;
  allCases: FeaturedCase[];
  upsertConfig: (config: {
    source_id: string;
    bbk_id?: string | null;
    case_ids: { case_id: string; sort_order: number }[];
  }) => Promise<void>;
  getConfigDetail: (
    sourceId: string,
    bbkId?: string | null
  ) => Promise<{ source_id: string; bbk_id: string | null; case_ids: string[] }>;
}

export function ConfigDrawer({
  open,
  editingSourceId,
  editingBbkId,
  onClose,
  onSuccess,
  allCases,
  upsertConfig,
  getConfigDetail,
}: ConfigDrawerProps) {
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [selectedCaseIds, setSelectedCaseIds] = useState<string[]>([]);

  const isEdit = !!editingSourceId;

  // Load existing config detail when editing
  useEffect(() => {
    if (open && editingSourceId) {
      form.setFieldsValue({
        source_id: editingSourceId,
        bbk_id: editingBbkId || "",
      });
      setLoadingDetail(true);
      getConfigDetail(editingSourceId, editingBbkId)
        .then((detail) => {
          setSelectedCaseIds(detail.case_ids);
        })
        .catch(() => {
          setSelectedCaseIds([]);
        })
        .finally(() => {
          setLoadingDetail(false);
        });
    } else if (open) {
      form.resetFields();
      setSelectedCaseIds([]);
    }
  }, [open, editingSourceId, editingBbkId, form, getConfigDetail]);

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);

      const caseIds = selectedCaseIds.map((caseId, idx) => ({
        case_id: caseId,
        sort_order: idx,
      }));

      await upsertConfig({
        source_id: values.source_id,
        bbk_id: values.bbk_id || null,
        case_ids: caseIds,
      });

      message.success(isEdit ? "配置已更新" : "配置已创建");
      onSuccess();
      onClose();
    } catch (error) {
      // Validation error or API error
    } finally {
      setSaving(false);
    }
  };

  return (
    <Drawer
      width={500}
      placement="right"
      title={isEdit ? "编辑维度配置" : "新建维度配置"}
      open={open}
      onClose={onClose}
      destroyOnClose
      footer={
        <div style={{ display: "flex", gap: 8 }}>
          <Button onClick={onClose}>取消</Button>
          <Button type="primary" loading={saving} onClick={handleSubmit}>
            保存
          </Button>
        </div>
      }
    >
      <Form form={form} layout="vertical">
        <Form.Item
          name="source_id"
          label="Source ID"
          rules={[{ required: true, message: "请输入 Source ID" }]}
        >
          <Input placeholder="如 source-001" disabled={isEdit} />
        </Form.Item>

        <Form.Item name="bbk_id" label="BBK ID（可选）">
          <Input placeholder="如 bbk-001，留空表示仅按 source_id 匹配" disabled={isEdit} />
        </Form.Item>
      </Form>

      <div style={{ marginBottom: 8, fontWeight: 500 }}>选择案例</div>
      {loadingDetail ? (
        <Spin />
      ) : (
        <Checkbox.Group
          value={selectedCaseIds}
          onChange={(vals) => setSelectedCaseIds(vals as string[])}
          style={{ display: "flex", flexDirection: "column", gap: 8 }}
        >
          {allCases
            .filter((c) => c.is_active)
            .map((c) => (
              <Checkbox key={c.case_id} value={c.case_id}>
                <span style={{ marginRight: 8 }}>{c.case_id}</span>
                <span style={{ color: "#999" }}>
                  {c.label.length > 40 ? c.label.slice(0, 40) + "..." : c.label}
                </span>
              </Checkbox>
            ))}
        </Checkbox.Group>
      )}
    </Drawer>
  );
}
