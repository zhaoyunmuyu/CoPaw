import { useEffect, useMemo, useState } from "react";
import { Button, Input, Modal } from "@agentscope-ai/design";
import { CheckOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import type { PoolSkillSpec } from "../../../../api/types";
import styles from "../../Skills/index.module.less";

interface BroadcastModalProps {
  open: boolean;
  skills: PoolSkillSpec[];
  tenantIds: string[];
  initialSkillNames: string[];
  onCancel: () => void;
  onConfirm: (skillNames: string[], tenantIds: string[]) => Promise<void>;
}

function parseManualTenantIds(input: string): string[] {
  return Array.from(
    new Set(
      input
        .split(/[\s,]+/)
        .map((item) => item.trim())
        .filter(Boolean),
    ),
  );
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
  const [manualTenantIdsText, setManualTenantIdsText] = useState("");

  const builtinSkillNames = useMemo(
    () => skills.filter((s) => s.source === "builtin").map((s) => s.name),
    [skills],
  );

  const manualTenantIds = useMemo(
    () => parseManualTenantIds(manualTenantIdsText),
    [manualTenantIdsText],
  );

  useEffect(() => {
    if (open) {
      setSelectedSkillNames(initialSkillNames);
      setSelectedTenantIds([]);
      setManualTenantIdsText("");
    }
  }, [open, initialSkillNames]);

  const handleCancel = () => {
    setSelectedSkillNames([]);
    setSelectedTenantIds([]);
    setManualTenantIdsText("");
    onCancel();
  };

  const targetTenantIds = Array.from(
    new Set([...selectedTenantIds, ...manualTenantIds]),
  );

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

        <div className={styles.pickerSection}>
          <div className={styles.pickerHeader}>
            <div className={styles.pickerLabel}>
              {t("skillPool.selectWorkspaces")}
            </div>
            <div className={styles.bulkActions}>
              <Button
                size="small"
                onClick={() => setSelectedTenantIds(Array.from(new Set(tenantIds)))}
              >
                {t("skillPool.allWorkspaces")}
              </Button>
              <Button size="small" onClick={() => setSelectedTenantIds([])}>
                {t("skills.clearSelection")}
              </Button>
            </div>
          </div>
          <div style={{ marginTop: 8, color: "#666", fontSize: 12 }}>
            {t("skillPool.broadcastHint")}
          </div>
        </div>

        <div className={`${styles.pickerGrid} ${styles.compactPickerGrid}`}>
          {tenantIds.map((tenantId) => {
            const selected = selectedTenantIds.includes(tenantId);
            return (
              <div
                key={tenantId}
                className={`${styles.pickerCard} ${styles.compactPickerCard} ${
                  selected ? styles.pickerCardSelected : ""
                }`}
                onClick={() =>
                  setSelectedTenantIds(
                    selected
                      ? selectedTenantIds.filter((id) => id !== tenantId)
                      : [...selectedTenantIds, tenantId],
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
                  {tenantId}
                </div>
              </div>
            );
          })}
        </div>

        <div className={styles.pickerSection}>
          <div className={styles.pickerHeader}>
            <div className={styles.pickerLabel}>
              {t("skillPool.manualTenantIds")}
            </div>
          </div>
          <div style={{ marginTop: 8, marginBottom: 8, color: "#666", fontSize: 12 }}>
            {t("skillPool.manualTenantHint")}
          </div>
          <Input.TextArea
            rows={4}
            value={manualTenantIdsText}
            onChange={(event) => setManualTenantIdsText(event.target.value)}
            placeholder={t("skillPool.manualTenantPlaceholder")}
          />
        </div>
      </div>
    </Modal>
  );
}
