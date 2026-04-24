import type { ColumnType } from "antd/es/table";
import type { FeaturedCase } from "@/api/types/featuredCases";

interface CreateCaseColumnsOptions {
  onEdit: (caseItem: FeaturedCase) => void;
  onDelete: (caseId: string) => void;
}

export function createCaseColumns({
  onEdit,
  onDelete,
}: CreateCaseColumnsOptions): ColumnType<FeaturedCase>[] {
  return [
    {
      title: "案例 ID",
      dataIndex: "case_id",
      key: "case_id",
      width: 180,
      ellipsis: true,
    },
    {
      title: "BBK ID",
      dataIndex: "bbk_id",
      key: "bbk_id",
      width: 120,
      render: (bbkId: string | null) =>
        bbkId || <span style={{ color: "#999" }}>-</span>,
    },
    {
      title: "标题",
      dataIndex: "label",
      key: "label",
      ellipsis: true,
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
          <a
            onClick={() => onDelete(record.case_id)}
            style={{ color: "#ff4d4f" }}
          >
            删除
          </a>
        </span>
      ),
    },
  ];
}