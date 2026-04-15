import type { ColumnType } from "antd/es/table";
import type { Case } from "@/api/types/cases";

interface CreateColumnsOptions {
  onEdit: (caseItem: Case) => void;
  onDelete: (caseId: string) => void;
}

export function createColumns({
  onEdit,
  onDelete,
}: CreateColumnsOptions): ColumnType<Case>[] {
  return [
    {
      title: "ID",
      dataIndex: "id",
      key: "id",
      width: 180,
      ellipsis: true,
    },
    {
      title: "标题",
      dataIndex: "label",
      key: "label",
      ellipsis: true,
    },
    {
      title: "iframe_url",
      dataIndex: ["detail", "iframe_url"],
      key: "iframe_url",
      width: 200,
      ellipsis: true,
      render: (url: string) => url || "-",
    },
    {
      title: "排序",
      dataIndex: "sort_order",
      key: "sort_order",
      width: 80,
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