import AgentScopeRuntimeResponseCard from "@/components/agentscope-chat/AgentScopeRuntimeWebUI/core/AgentScopeRuntime/Response/Card";
import ChatMessageMeta from "../ChatMessageMeta";
import type { ChatRuntimeResponseCardData } from "../../messageMeta";
import styles from "../ChatMessageMeta/index.module.less";

const ASSISTANT_MESSAGE_NAME = "小助 Claw";

export default function RuntimeResponseCard(props: {
  data: ChatRuntimeResponseCardData;
  isLast?: boolean;
}) {
  return (
    <div className={styles.messageBlockStart}>
      <ChatMessageMeta
        align="start"
        name={ASSISTANT_MESSAGE_NAME}
        timestamp={props.data.headerMeta?.timestamp}
      />
      <AgentScopeRuntimeResponseCard data={props.data} isLast={props.isLast} />
    </div>
  );
}
