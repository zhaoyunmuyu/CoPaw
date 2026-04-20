import { formatMessageTime } from "../../messageMeta";
import styles from "./index.module.less";

export default function ChatMessageMeta(props: {
  align: "start" | "end";
  name: string;
  timestamp?: number;
}) {
  const wrapperClass =
    props.align === "end" ? styles.messageMetaEnd : styles.messageMetaStart;
  const timeLabel = formatMessageTime(props.timestamp);

  return (
    <div className={wrapperClass}>
      <span className={styles.messageMetaName}>{props.name}</span>
      {timeLabel ? (
        <time className={styles.messageMetaTime}>{timeLabel}</time>
      ) : null}
    </div>
  );
}
