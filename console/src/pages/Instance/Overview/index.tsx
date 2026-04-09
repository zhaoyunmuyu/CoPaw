import { useEffect, useState, useCallback } from "react";
import { Card, Row, Col, Statistic, Spin } from "antd";
import {
  SparkComputerLine,
  SparkUserGroupLine,
  SparkWarningCircleLine,
  SparkErrorCircleLine,
} from "@agentscope-ai/icons";
import { useTranslation } from "react-i18next";
import { instanceApi, type OverviewStats } from "../../../api/modules/instance";
import { PageHeader } from "@/components/PageHeader";
import styles from "./index.module.less";

export default function OverviewPage() {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState<OverviewStats | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const result = await instanceApi.getOverview();
      setStats(result);
    } catch (error) {
      console.error("Failed to fetch overview:", error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return (
    <div className={styles.overviewPage}>
      <PageHeader
        items={[{ title: t("nav.instance") }, { title: t("instance.overview") }]}
      />

      <Spin spinning={loading}>
        <Row gutter={[16, 16]}>
          <Col xs={24} sm={12} lg={6}>
            <Card className={styles.statCard}>
              <Statistic
                title={t("instance.totalInstances")}
                value={stats?.total_instances || 0}
                prefix={<SparkComputerLine size={20} />}
              />
            </Card>
          </Col>
          <Col xs={24} sm={12} lg={6}>
            <Card className={styles.statCard}>
              <Statistic
                title={t("instance.totalUsers")}
                value={stats?.total_users || 0}
                prefix={<SparkUserGroupLine size={20} />}
              />
            </Card>
          </Col>
          <Col xs={24} sm={12} lg={6}>
            <Card className={styles.statCard}>
              <Statistic
                title={t("instance.warningInstances")}
                value={stats?.warning_instances || 0}
                valueStyle={{ color: "#fa8c16" }}
                prefix={<SparkWarningCircleLine size={20} />}
              />
            </Card>
          </Col>
          <Col xs={24} sm={12} lg={6}>
            <Card className={styles.statCard}>
              <Statistic
                title={t("instance.criticalInstances")}
                value={stats?.critical_instances || 0}
                valueStyle={{ color: "#f5222d" }}
                prefix={<SparkErrorCircleLine size={20} />}
              />
            </Card>
          </Col>
        </Row>
      </Spin>
    </div>
  );
}
