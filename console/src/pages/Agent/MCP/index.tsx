import { useEffect, useState } from "react";
import { Button, Empty, Modal, Input } from "@agentscope-ai/design";
import { PlusOutlined, SendOutlined } from "@ant-design/icons";
import api from "../../../api";
import type { MCPClientInfo } from "../../../api/types";
import { TenantTargetPicker } from "../../../components/TenantTargetPicker";
import { useAppMessage } from "../../../hooks/useAppMessage";
import { MCPClientCard } from "./components";
import { useMCP } from "./useMCP";
import { useTranslation } from "react-i18next";
import { PageHeader } from "@/components/PageHeader";
import { useAgentStore } from "../../../stores/agentStore";
import { getUserId } from "../../../utils/identity";
import styles from "./index.module.less";

type MCPTransport = "stdio" | "streamable_http" | "sse";

function normalizeTransport(raw?: unknown): MCPTransport | undefined {
  if (typeof raw !== "string") return undefined;
  const value = raw.trim().toLowerCase();
  switch (value) {
    case "stdio":
      return "stdio";
    case "sse":
      return "sse";
    case "streamablehttp":
    case "streamable_http":
    case "streamable-http":
    case "http":
      return "streamable_http";
    default:
      return undefined;
  }
}

function normalizeClientData(key: string, rawData: any) {
  const transport =
    normalizeTransport(rawData.transport ?? rawData.type) ??
    (rawData.url || rawData.baseUrl || !rawData.command
      ? "streamable_http"
      : "stdio");

  const command =
    transport === "stdio" ? (rawData.command ?? "").toString() : "";

  return {
    name: rawData.name || key,
    description: rawData.description || "",
    enabled: rawData.enabled ?? rawData.isActive ?? true,
    transport,
    url: (rawData.url || rawData.baseUrl || "").toString(),
    headers: rawData.headers || {},
    command,
    args: Array.isArray(rawData.args) ? rawData.args : [],
    env: rawData.env || {},
    cwd: (rawData.cwd || "").toString(),
  };
}

function MCPPage() {
  const { t } = useTranslation();
  const { message } = useAppMessage();
  const { selectedAgent } = useAgentStore();
  const currentTenantId = getUserId();
  const {
    clients,
    loading,
    toggleEnabled,
    deleteClient,
    createClient,
    updateClient,
    loadClients,
  } = useMCP();
  const [hoverKey, setHoverKey] = useState<string | null>(null);
  const [selectedClientKeys, setSelectedClientKeys] = useState<string[]>([]);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [distributionOpen, setDistributionOpen] = useState(false);
  const [distributionLoading, setDistributionLoading] = useState(false);
  const [distributionSubmitting, setDistributionSubmitting] = useState(false);
  const [distributionTenantIds, setDistributionTenantIds] = useState<string[]>([]);
  const [selectedTenantIds, setSelectedTenantIds] = useState<string[]>([]);
  const sanitizedSelectedTenantIds = selectedTenantIds.filter(
    (tenantId) => tenantId !== currentTenantId,
  );
  const [newClientJson, setNewClientJson] = useState(`{
  "mcpServers": {
    "example-client": {
      "command": "npx",
      "args": ["-y", "@example/mcp-server"],
      "env": {
        "API_KEY": "<YOUR_API_KEY>"
      }
    }
  }
}`);

  const handleToggleEnabled = async (
    client: MCPClientInfo,
    e?: React.MouseEvent,
  ) => {
    e?.stopPropagation();
    await toggleEnabled(client);
  };

  const handleDelete = async (client: MCPClientInfo, e?: React.MouseEvent) => {
    e?.stopPropagation();
    await deleteClient(client);
  };

  useEffect(() => {
    setSelectedClientKeys((current) =>
      current.filter((clientKey) =>
        clients.some((client) => client.key === clientKey),
      ),
    );
  }, [clients]);

  const handleToggleSelectedClient = (clientKey: string) => {
    setSelectedClientKeys((current) =>
      current.includes(clientKey)
        ? current.filter((item) => item !== clientKey)
        : [...current, clientKey],
    );
  };

  const openDistributionModal = async () => {
    if (!selectedClientKeys.length) return;

    setDistributionOpen(true);
    setSelectedTenantIds([]);
    setDistributionLoading(true);
    try {
      const result = await api.listMCPDistributionTenants();
      setDistributionTenantIds(
        (result.tenant_ids || []).filter(
          (tenantId) => tenantId !== currentTenantId,
        ),
      );
    } catch (error) {
      const errMsg =
        error instanceof Error ? error.message : t("mcp.distributeFailed");
      message.error(errMsg);
    } finally {
      setDistributionLoading(false);
    }
  };

  const closeDistributionModal = () => {
    if (distributionSubmitting) return;
    setDistributionOpen(false);
    setSelectedTenantIds([]);
  };

  const handleDistributeSelectedClients = async () => {
    if (!selectedClientKeys.length || !sanitizedSelectedTenantIds.length) return;

    setDistributionSubmitting(true);
    try {
      const result = await api.distributeMCPClientsToDefaultAgents({
        client_keys: selectedClientKeys,
        target_tenant_ids: sanitizedSelectedTenantIds,
        overwrite: true,
      });
      const items = Array.isArray(result.results) ? result.results : [];
      const succeeded = items.filter((item) => item.success);
      const failed = items.filter((item) => !item.success);

      if (succeeded.length > 0) {
        const lines = succeeded.map((item) => {
          const suffix = item.bootstrapped
            ? ` (${t("mcp.distributeBootstrapped")})`
            : "";
          return `• ${item.tenant_id}${suffix}`;
        });
        message.success(t("mcp.distributeSuccess", { count: succeeded.length }));
        Modal.confirm({
          title: t("mcp.distributeResultTitle"),
          content: (
            <div style={{ display: "grid", gap: 8 }}>
              <div>{t("mcp.distributeSuccessList")}</div>
              <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>
                {lines.join("\n")}
              </pre>
              {failed.length > 0 ? (
                <div>{t("mcp.distributeFailureInlineHint")}</div>
              ) : null}
            </div>
          ),
          okText: t("common.close"),
          cancelButtonProps: { style: { display: "none" } },
        });
      }

      if (failed.length > 0) {
        const failureLines = failed.map(
          (item) => `• ${item.tenant_id}: ${item.error || t("mcp.distributeFailed")}`,
        );
        if (succeeded.length === 0) {
          message.error(t("mcp.distributeFailed"));
        }
        Modal.confirm({
          title: t("mcp.distributePartialFailureTitle"),
          content: (
            <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>
              {failureLines.join("\n")}
            </pre>
          ),
          okText: t("common.close"),
          cancelButtonProps: { style: { display: "none" } },
        });
      }

      setDistributionOpen(false);
      setSelectedTenantIds([]);
      setSelectedClientKeys([]);
      await loadClients();
    } catch (error) {
      const errMsg =
        error instanceof Error ? error.message : t("mcp.distributeFailed");
      message.error(errMsg);
    } finally {
      setDistributionSubmitting(false);
    }
  };

  const handleCreateClient = async () => {
    try {
      const parsed = JSON.parse(newClientJson);

      // Support two formats:
      // Format 1: { "mcpServers": { "key": { "command": "...", ... } } }
      // Format 2: { "key": { "command": "...", ... } }
      // Format 3: { "key": "...", "name": "...", "command": "...", ... } (direct)

      const clientsToCreate: Array<{ key: string; data: any }> = [];

      if (parsed.mcpServers) {
        // Format 1: nested mcpServers
        Object.entries(parsed.mcpServers).forEach(
          ([key, data]: [string, any]) => {
            clientsToCreate.push({
              key,
              data: normalizeClientData(key, data),
            });
          },
        );
      } else if (
        parsed.key &&
        (parsed.command || parsed.url || parsed.baseUrl)
      ) {
        // Format 3: direct format with key field
        const { key, ...clientData } = parsed;
        clientsToCreate.push({
          key,
          data: normalizeClientData(key, clientData),
        });
      } else {
        // Format 2: direct client objects with keys
        Object.entries(parsed).forEach(([key, data]: [string, any]) => {
          if (
            typeof data === "object" &&
            (data.command || data.url || data.baseUrl)
          ) {
            clientsToCreate.push({
              key,
              data: normalizeClientData(key, data),
            });
          }
        });
      }

      // Create all clients
      let allSuccess = true;
      for (const { key, data } of clientsToCreate) {
        const success = await createClient(key, data);
        if (!success) allSuccess = false;
      }

      if (allSuccess) {
        setCreateModalOpen(false);
        setNewClientJson(`{
  "mcpServers": {
    "example-client": {
      "command": "npx",
      "args": ["-y", "@example/mcp-server"],
      "env": {
        "API_KEY": "<YOUR_API_KEY>"
      }
    }
  }
}`);
      }
    } catch (error) {
      alert("Invalid JSON format");
    }
  };

  return (
    <div className={styles.mcpPage}>
      <PageHeader
        items={[{ title: t("nav.agent") }, { title: t("mcp.title") }]}
        extra={
          <div className={styles.headerActions}>
            {selectedClientKeys.length > 0 ? (
              <span className={styles.selectionSummary}>
                {t("mcp.selectedCount", { count: selectedClientKeys.length })}
              </span>
            ) : null}
            <Button
              disabled={!selectedClientKeys.length}
              icon={<SendOutlined />}
              onClick={openDistributionModal}
            >
              {t("mcp.distribute")}
            </Button>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => setCreateModalOpen(true)}
            >
              {t("mcp.create")}
            </Button>
          </div>
        }
      />

      {loading ? (
        <div className={styles.loading}>
          <p>{t("common.loading")}</p>
        </div>
      ) : clients.length === 0 ? (
        <Empty description={t("mcp.emptyState")} />
      ) : (
        <div className={styles.mcpGrid}>
          {clients.map((client) => (
            <MCPClientCard
              key={client.key}
              client={client}
              onToggle={handleToggleEnabled}
              onDelete={handleDelete}
              onUpdate={updateClient}
              selected={selectedClientKeys.includes(client.key)}
              onSelectToggle={handleToggleSelectedClient}
              isHovered={hoverKey === client.key}
              onMouseEnter={() => setHoverKey(client.key)}
              onMouseLeave={() => setHoverKey(null)}
            />
          ))}
        </div>
      )}

      <Modal
        open={distributionOpen}
        title={t("mcp.distributeTitle")}
        onCancel={closeDistributionModal}
        onOk={handleDistributeSelectedClients}
        okButtonProps={{
          disabled: !sanitizedSelectedTenantIds.length,
          loading: distributionSubmitting,
        }}
      >
        <div style={{ display: "grid", gap: 12 }}>
          <div style={{ color: "#666", fontSize: 12 }}>{t("mcp.distributeHint")}</div>
          <div style={{ fontWeight: 500 }}>
            {t("mcp.distributeCurrentSource", {
              agent: selectedAgent || "default",
              count: selectedClientKeys.length,
            })}
          </div>
          <div className={styles.distributionWarning}>
            <div>{t("mcp.distributeDefaultAgentWarning")}</div>
            <div>{t("mcp.distributeOverwriteWarning")}</div>
          </div>
          {distributionLoading ? (
            <div>{t("common.loading")}</div>
          ) : (
            <TenantTargetPicker
              tenantIds={distributionTenantIds}
              selectedTenantIds={selectedTenantIds}
              onChange={(tenantIds) =>
                setSelectedTenantIds(
                  tenantIds.filter((tenantId) => tenantId !== currentTenantId),
                )
              }
            />
          )}
        </div>
      </Modal>

      <Modal
        title={t("mcp.create")}
        open={createModalOpen}
        onCancel={() => setCreateModalOpen(false)}
        footer={
          <div className={styles.modalFooter}>
            <Button
              onClick={() => setCreateModalOpen(false)}
              style={{ marginRight: 8 }}
            >
              {t("common.cancel")}
            </Button>
            <Button type="primary" onClick={handleCreateClient}>
              {t("common.create")}
            </Button>
          </div>
        }
        width={800}
      >
        <div className={styles.importHint}>
          <p className={styles.importHintTitle}>{t("mcp.formatSupport")}:</p>
          <ul className={styles.importHintList}>
            <li>
              {t("mcp.standardFormat")}:{" "}
              <code>{`{ "mcpServers": { "key": {...} } }`}</code>
            </li>
            <li>
              {t("mcp.directFormat")}: <code>{`{ "key": {...} }`}</code>
            </li>
            <li>
              {t("mcp.singleFormat")}:{" "}
              <code>{`{ "key": "...", "name": "...", "command": "..." }`}</code>
            </li>
          </ul>
        </div>
        <Input.TextArea
          value={newClientJson}
          onChange={(e) => setNewClientJson(e.target.value)}
          autoSize={{ minRows: 15, maxRows: 25 }}
          className={styles.jsonTextArea}
        />
      </Modal>
    </div>
  );
}

export default MCPPage;
