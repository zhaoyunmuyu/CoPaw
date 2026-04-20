import { Drawer, Form, Input, Switch, Button } from "@agentscope-ai/design";
import type { FormInstance } from "antd";
import type { GreetingConfig } from "@/api/types/greeting";

interface GreetingDrawerProps {
  open: boolean;
  editingConfig: GreetingConfig | null;
  form: FormInstance<GreetingConfig>;
  saving: boolean;
  onClose: () => void;
  onSubmit: (values: GreetingConfig) => void;
}

const DEFAULT_CONFIG: Partial<GreetingConfig> = {
  bbk_id: null,
  subtitle: "",
  placeholder: "",
  is_active: true,
};

export function GreetingDrawer({
  open,
  editingConfig,
  form,
  saving,
  onClose,
  onSubmit,
}: GreetingDrawerProps) {
  return (
    <Drawer
      width={500}
      placement="right"
      title={editingConfig ? "编辑配置" : "新建配置"}
      open={open}
      onClose={onClose}
      destroyOnClose
      footer={
        <div style={{ display: "flex", gap: 8 }}>
          <Button onClick={onClose}>取消</Button>
          <Button type="primary" loading={saving} onClick={() => form.submit()}>
            保存
          </Button>
        </div>
      }
    >
      <Form
        form={form}
        layout="vertical"
        onFinish={onSubmit}
        initialValues={DEFAULT_CONFIG}
      >
        <Form.Item
          name="source_id"
          label="Source ID"
          rules={[{ required: true, message: "请输入 Source ID" }]}
        >
          <Input
            placeholder="如 source-001"
            disabled={!!editingConfig}
          />
        </Form.Item>

        <Form.Item name="bbk_id" label="BBK ID（可选）">
          <Input placeholder="如 bbk-001，留空表示仅按 source_id 匹配" />
        </Form.Item>

        <Form.Item
          name="greeting"
          label="欢迎语"
          rules={[{ required: true, message: "请输入欢迎语" }]}
        >
          <Input.TextArea
            placeholder="你好，欢迎来到智能助手！"
            autoSize={{ minRows: 2, maxRows: 4 }}
          />
        </Form.Item>

        <Form.Item name="subtitle" label="副标题">
          <Input.TextArea
            placeholder="我可以帮你分析数据、撰写报告"
            autoSize={{ minRows: 1, maxRows: 2 }}
          />
        </Form.Item>

        <Form.Item name="placeholder" label="输入框占位符">
          <Input placeholder="输入你的问题..." />
        </Form.Item>

        <Form.Item name="is_active" label="启用" valuePropName="checked">
          <Switch />
        </Form.Item>
      </Form>
    </Drawer>
  );
}
