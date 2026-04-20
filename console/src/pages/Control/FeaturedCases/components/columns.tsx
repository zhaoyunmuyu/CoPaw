import type { ColumnType } from "antd/es/table";
import type { FeaturedCase, CaseConfigListItem } from "@/api/types/featuredCases";

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
      title: "标题",
      dataIndex: "label",
      key: "label",
      ellipsis: true,
    },
    {
      title: "iframe_url",
      dataIndex: "iframe_url",
      key: "iframe_url",
      width: 200,
      ellipsis: true,
      render: (url: string) => url || "-",
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

interface CreateConfigColumnsOptions {
  onConfig: (config: CaseConfigListItem) => void;
  onDelete: (config: CaseConfigListItem) => void;
}

export function createConfigColumns({
  onConfig,
  onDelete,
}: CreateConfigColumnsOptions): ColumnType<CaseConfigListItem>[] {
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
      render: (bbkId: string | null) =>
        bbkId || <span style={{ color: "#999" }}>-</span>,
    },
    {
      title: "案例数",
      dataIndex: "case_count",
      key: "case_count",
      width: 100,
    },
    {
      title: "操作",
      key: "action",
      width: 150,
      render: (_, record) => (
        <span>
          <a onClick={() => onConfig(record)} style={{ marginRight: 12 }}>
            配置
          </a>
          <a
            onClick={() => onDelete(record)}
            style={{ color: "#ff4d4f" }}
          >
            删除
          </a>
        </span>
      ),
    },
  ];
}
