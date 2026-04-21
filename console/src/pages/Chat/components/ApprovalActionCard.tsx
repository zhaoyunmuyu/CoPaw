import { useMemo, useState } from "react";
import { Button, Flex } from "antd";
import { OperateCard } from "@/components/agentscope-chat";
import { emit } from "@/components/agentscope-chat/AgentScopeRuntimeWebUI/core/Context/useChatAnywhereEventEmitter";
import type { ChatApprovalActionCardData } from "../messageMeta";

export default function ApprovalActionCard(props: {
  data: ChatApprovalActionCardData;
}) {
  const { data } = props;
  const [submitted, setSubmitted] = useState(false);

  const paramsText = useMemo(
    () => JSON.stringify(data.toolInput ?? {}, null, 2),
    [data.toolInput],
  );

  const handleAction = (query: string) => {
    if (submitted) return;
    emit({
      type: "handleSubmit",
      data: { query, fileList: [] },
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
