import type { ColumnType } from "antd/es/table";
import type { GreetingConfig } from "@/api/types/greeting";

interface CreateColumnsOptions {
  onEdit: (config: GreetingConfig) => void;
  onDelete: (id: number) => void;
}

export function createColumns({
  onEdit,
  onDelete,
}: CreateColumnsOptions): ColumnType<GreetingConfig>[] {
  return [
    {
      title: "Source ID",
      dataIndex: "source_id",
      key: "source_id",
      width: 150,
    },
    {
      title: "BBK ID",
      dataIndex: "bbk_id",
      key: "bbk_id",
      width: 120,
      render: (bbkId: string | null) => bbkId || <span style={{ color: "#999" }}>-</span>,
    },
    {
      title: "欢迎语",
      dataIndex: "greeting",
      key: "greeting",
      ellipsis: true,
    },
    {
      title: "副标题",
      dataIndex: "subtitle",
      key: "subtitle",
      width: 200,
      ellipsis: true,
      render: (subtitle: string) => subtitle || "-",
    },
    {
      title: "占位符",
      dataIndex: "placeholder",
      key: "placeholder",
      width: 150,
      ellipsis: true,
      render: (placeholder: string) => placeholder || "-",
    },
    {
      title: "状态",
      dataIndex: "is_active",
      key: "is_active",
      width: 80,
      render: (active: boolean) =>
        active ? (
          <span style={{ color: "#52c41a" }}>启用</span>
        ) : (
          <span style={{ color: "#999" }}>禁用</span>
        ),
    },
    {
      title: "操作",
      key: "action",
      width: 120,
      render: (_, record) => (
        <span>
          <a onClick={() => onEdit(record)} style={{ marginRight: 12 }}>
            编辑
          </a>
          <a onClick={() => onDelete(record.id)} style={{ color: "#ff4d4f" }}>
            删除
          </a>
        </span>
      ),
    },
  ];
}
