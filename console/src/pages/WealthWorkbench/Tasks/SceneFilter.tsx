import { useRef, useState } from "react";
import { Dropdown, Tooltip } from "antd";
import cx from "classnames";
import styles from "../index.module.less";

const FILTER_LABEL = "筛选经营场景";

export function SceneFilter({
  value,
  options,
  onChange,
}: {
  value: string | null;
  options: string[];
  onChange: (value: string | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const active = value !== null;
  const apply = (next: string | null) => {
    onChange(next);
    setOpen(false);
    requestAnimationFrame(() => triggerRef.current?.focus());
  };

  return (
    <>
      <Dropdown
        autoFocus
        trigger={["click"]}
        open={open}
        onOpenChange={setOpen}
        menu={{
          "aria-label": FILTER_LABEL,
          selectable: true,
          selectedKeys: [active ? `scene:${value}` : "all"],
          style: {
            maxHeight: "50vh",
            overflowY: "auto",
            maxWidth: "min(320px, calc(100vw - 20px))",
          },
          items: [
            { key: "all", label: "全部场景" },
            ...options.map((name) => ({
              key: `scene:${name}`,
              label: <span className={styles.sceneFilterName}>{name}</span>,
            })),
          ],
          onClick: ({ key, domEvent }) => {
            domEvent.stopPropagation();
            apply(key === "all" ? null : key.slice(6));
          },
        }}
      >
        <button
          type="button"
          ref={triggerRef}
          className={cx(styles.tagFilterTrigger, active && styles.filtered)}
          aria-label={FILTER_LABEL + (active ? `，当前：${value}` : "")}
          aria-haspopup="menu"
          aria-expanded={open}
        >
          <span>经营场景</span>
          <span className={styles.tagFilterIcon}>
            <svg viewBox="0 0 20 20" aria-hidden="true">
              <path d="M3 4h14l-5.5 6v5l-3 1v-6Z" />
            </svg>
            {active && <i />}
          </span>
        </button>
      </Dropdown>
      {active && (
        <div className={cx(styles.tagFilterApplied, styles.sceneFilterApplied)}>
          <Tooltip
            trigger={["hover", "focus"]}
            title={
              <div className={styles.opportunityTooltipContent}>{value}</div>
            }
          >
            <span tabIndex={0}>{value}</span>
          </Tooltip>
          <button
            type="button"
            aria-label="清除经营场景筛选"
            onClick={() => apply(null)}
          >
            ×
          </button>
        </div>
      )}
    </>
  );
}
