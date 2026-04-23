import { useEffect, useState } from "react";
import { Button, Flex } from "antd";
import { OperateCard } from "@/components/agentscope-chat";
import { emit } from "@/components/agentscope-chat/AgentScopeRuntimeWebUI/core/Context/useChatAnywhereEventEmitter";
import type { ChatApprovalActionCardData } from "../messageMeta";

const APPROVAL_ACTION_STORAGE_KEY = "copaw_submitted_approval_requests";

function loadSubmittedApprovalIds(): Set<string> {
  try {
    const raw = sessionStorage.getItem(APPROVAL_ACTION_STORAGE_KEY);
    if (!raw) return new Set();
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return new Set();
    return new Set(
      parsed.filter((item): item is string => typeof item === "string"),
    );
  } catch {
    return new Set();
  }
}

function storeSubmittedApprovalId(requestId: string): void {
  if (!requestId) return;
  const submittedIds = loadSubmittedApprovalIds();
  submittedIds.add(requestId);
  try {
    sessionStorage.setItem(
      APPROVAL_ACTION_STORAGE_KEY,
      JSON.stringify(Array.from(submittedIds)),
    );
  } catch {
    // Ignore storage write failures and keep the in-memory disabled state.
  }
}

export default function ApprovalActionCard(props: {
  data: ChatApprovalActionCardData;
}) {
  const { data } = props;
  const [submitted, setSubmitted] = useState(false);
  const resolvedByBackend = !!data.status && data.status !== "pending";

  useEffect(() => {
    setSubmitted(
      resolvedByBackend || loadSubmittedApprovalIds().has(data.requestId),
    );
  }, [data.requestId, resolvedByBackend]);

  const handleAction = (query: string) => {
    if (submitted) return;
    storeSubmittedApprovalId(data.requestId);
    setSubmitted(true);
    emit({
      type: "handleSubmit",
      data: { query, fileList: [] },
    });
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
