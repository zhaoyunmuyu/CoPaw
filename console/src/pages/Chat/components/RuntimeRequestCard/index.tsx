import AgentScopeRuntimeRequestCard from "@/components/agentscope-chat/AgentScopeRuntimeWebUI/core/AgentScopeRuntime/Request/Card";
import ChatMessageMeta from "../ChatMessageMeta";
import type { ChatRuntimeRequestCardData } from "../../messageMeta";
import styles from "../ChatMessageMeta/index.module.less";

export default function RuntimeRequestCard(props: {
  data: ChatRuntimeRequestCardData;
}) {
  return (
    <div className={styles.messageBlockEnd}>
      <ChatMessageMeta
        align="end"
        name="我"
        timestamp={props.data.headerMeta?.timestamp}
      />
      <AgentScopeRuntimeRequestCard data={props.data} />
    </div>
  );
}
