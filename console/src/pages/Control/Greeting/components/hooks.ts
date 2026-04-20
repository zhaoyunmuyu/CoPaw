import { useState, useEffect, useCallback } from "react";
import { greetingApi } from "@/api/modules/greeting";
import type { GreetingConfig } from "@/api/types/greeting";

export function useGreeting() {
  const [configs, setConfigs] = useState<GreetingConfig[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);

  const loadConfigs = useCallback(
    async (params?: { source_id?: string; page?: number; page_size?: number }) => {
      setLoading(true);
      try {
        const data = await greetingApi.listConfigs(params);
        setConfigs(data.configs);
        setTotal(data.total);
      } catch (error) {
        console.error("Failed to load greeting configs:", error);
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const createConfig = useCallback(async (config: GreetingConfig) => {
    try {
      const result = await greetingApi.createConfig(config);
      return result.data;
    } catch (error) {
      console.error("Failed to create greeting config:", error);
      throw error;
    }
  }, []);

  const updateConfig = useCallback(async (id: number, config: Partial<GreetingConfig>) => {
    try {
      const result = await greetingApi.updateConfig(id, config);
      return result.data;
    } catch (error) {
      console.error("Failed to update greeting config:", error);
      throw error;
    }
  }, []);

  const deleteConfig = useCallback(async (id: number) => {
    try {
      await greetingApi.deleteConfig(id);
    } catch (error) {
      console.error("Failed to delete greeting config:", error);
      throw error;
    }
  }, []);

  return {
    configs,
    loading,
    total,
    loadConfigs,
    createConfig,
    updateConfig,
    deleteConfig,
  };
}
