import { useMemo, useState } from "react";
import { Button, Flex } from "antd";
import { OperateCard } from "@/components/agentscope-chat";
import type { ChatApprovalActionCardData } from "../messageMeta";

type ApprovalActionCardContext = {
  onInput?: {
    onSubmit?: (data: { query: string; fileList?: unknown[] }) => void;
  };
};

export default function ApprovalActionCard(props: {
  data: ChatApprovalActionCardData;
  context?: ApprovalActionCardContext;
}) {
  const { data, context } = props;
  const [submitted, setSubmitted] = useState(false);

  const paramsText = useMemo(
    () => JSON.stringify(data.toolInput ?? {}, null, 2),
    [data.toolInput],
  );

  const handleAction = (query: string) => {
    if (submitted) return;
    context?.onInput?.onSubmit?.({
      query,
      fileList: [],
    });
    setSubmitted(true);
  };

  return (
    <OperateCard
      header={{
        icon: <span>⏳</span>,
        title: "等待审批",
        description: data.toolName,
      }}
      body={{
        defaultOpen: true,
        children: (
          <OperateCard.LineBody>
            <div style={{ marginBottom: 12 }}>触发来源：{data.triggerLabel}</div>
            <pre
              style={{
                margin: 0,
                padding: 12,
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
                overflowX: "auto",
              }}
            >
              {paramsText}
            </pre>
            <Flex gap={8} style={{ marginTop: 12 }}>
              <Button
                data-testid="approval-approve"
                type="primary"
                disabled={submitted}
                onClick={() => handleAction(data.approveCommand)}
              >
                同意
              </Button>
              <Button
                data-testid="approval-deny"
                disabled={submitted}
                onClick={() => handleAction(data.denyCommand)}
              >
                拒绝
              </Button>
            </Flex>
          </OperateCard.LineBody>
        ),
      }}
    />
  );
}
