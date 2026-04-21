import { useEffect, useMemo, useState } from "react";
import { Button, Modal } from "@agentscope-ai/design";
import { CheckOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import type { PoolSkillSpec } from "../../../../api/types";
import { TenantTargetPicker } from "../../../../components/TenantTargetPicker";
import styles from "../../Skills/index.module.less";

interface BroadcastModalProps {
  open: boolean;
  skills: PoolSkillSpec[];
  tenantIds: string[];
  initialSkillNames: string[];
  onCancel: () => void;
  onConfirm: (skillNames: string[], tenantIds: string[]) => Promise<void>;
}

export function BroadcastModal({
  open,
  skills,
  tenantIds,
  initialSkillNames,
  onCancel,
  onConfirm,
}: BroadcastModalProps) {
  const { t } = useTranslation();
  const [selectedSkillNames, setSelectedSkillNames] =
    useState<string[]>(initialSkillNames);
  const [selectedTenantIds, setSelectedTenantIds] = useState<string[]>([]);

  const builtinSkillNames = useMemo(
    () => skills.filter((s) => s.source === "builtin").map((s) => s.name),
    [skills],
  );

  useEffect(() => {
    if (open) {
      setSelectedSkillNames(initialSkillNames);
      setSelectedTenantIds([]);
    }
  }, [open, initialSkillNames]);

  const handleCancel = () => {
    setSelectedSkillNames([]);
    setSelectedTenantIds([]);
    onCancel();
  };

  const targetTenantIds = Array.from(new Set(selectedTenantIds));

  return (
    <Modal
      open={open}
      onCancel={handleCancel}
      onOk={() => onConfirm(selectedSkillNames, targetTenantIds)}
      okButtonProps={{
        disabled:
          selectedSkillNames.length === 0 || targetTenantIds.length === 0,
      }}
      title={t("skillPool.broadcast")}
      width={640}
    >
      <div style={{ display: "grid", gap: 12 }}>
        <div className={styles.pickerSection}>
          <div className={styles.pickerHeader}>
            <div className={styles.pickerLabel}>{t("skills.selectPoolItem")}</div>
            <div className={styles.bulkActions}>
              <Button
                size="small"
                onClick={() => setSelectedSkillNames(skills.map((s) => s.name))}
              >
                {t("agent.selectAll")}
              </Button>
              <Button
                size="small"
                onClick={() => setSelectedSkillNames(builtinSkillNames)}
              >
                {t("agent.selectBuiltin")}
              </Button>
              <Button size="small" onClick={() => setSelectedSkillNames([])}>
                {t("skills.clearSelection")}
              </Button>
            </div>
          </div>
        </div>

        <div className={`${styles.pickerGrid} ${styles.compactPickerGrid}`}>
          {skills.map((skill) => {
            const selected = selectedSkillNames.includes(skill.name);
            return (
              <div
                key={skill.name}
                className={`${styles.pickerCard} ${styles.compactPickerCard} ${
                  selected ? styles.pickerCardSelected : ""
                }`}
                onClick={() =>
                  setSelectedSkillNames(
                    selected
                      ? selectedSkillNames.filter((n) => n !== skill.name)
                      : [...selectedSkillNames, skill.name],
                  )
                }
              >
                {selected && (
                  <span
                    className={`${styles.pickerCheck} ${styles.compactPickerCheck}`}
                  >
                    <CheckOutlined />
                  </span>
                )}
                <div
                  className={`${styles.pickerCardTitle} ${styles.compactPickerTitle}`}
                >
                  {skill.name}
                </div>
              </div>
            );
          })}
        </div>

        <TenantTargetPicker
          tenantIds={tenantIds}
          selectedTenantIds={selectedTenantIds}
          onChange={setSelectedTenantIds}
          hint={t("skillPool.broadcastHint")}
        />
      </div>
    </Modal>
  );
}
