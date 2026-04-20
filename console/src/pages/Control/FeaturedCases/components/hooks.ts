import { useState, useEffect, useCallback } from "react";
import { featuredCasesApi } from "@/api/modules/featuredCases";
import type {
  FeaturedCase,
  CaseConfigListItem,
} from "@/api/types/featuredCases";

export function useFeaturedCases() {
  const [cases, setCases] = useState<FeaturedCase[]>([]);
  const [casesLoading, setCasesLoading] = useState(false);
  const [casesTotal, setCasesTotal] = useState(0);

  const [configs, setConfigs] = useState<CaseConfigListItem[]>([]);
  const [configsLoading, setConfigsLoading] = useState(false);
  const [configsTotal, setConfigsTotal] = useState(0);

  const loadCases = useCallback(
    async (params?: { page?: number; page_size?: number }) => {
      setCasesLoading(true);
      try {
        const data = await featuredCasesApi.adminListCases(params);
        setCases(data.cases);
        setCasesTotal(data.total);
      } catch (error) {
        console.error("Failed to load cases:", error);
      } finally {
        setCasesLoading(false);
      }
    },
    []
  );

  const loadConfigs = useCallback(
    async (params?: { source_id?: string; page?: number; page_size?: number }) => {
      setConfigsLoading(true);
      try {
        const data = await featuredCasesApi.adminListConfigs(params);
        setConfigs(data.configs);
        setConfigsTotal(data.total);
      } catch (error) {
        console.error("Failed to load configs:", error);
      } finally {
        setConfigsLoading(false);
      }
    },
    []
  );

  const createCase = useCallback(async (caseItem: FeaturedCase) => {
    try {
      const result = await featuredCasesApi.adminCreateCase(caseItem);
      return result.data;
    } catch (error) {
      console.error("Failed to create case:", error);
      throw error;
    }
  }, []);

  const updateCase = useCallback(
    async (caseId: string, caseItem: Partial<FeaturedCase>) => {
      try {
        const result = await featuredCasesApi.adminUpdateCase(caseId, caseItem);
        return result.data;
      } catch (error) {
        console.error("Failed to update case:", error);
        throw error;
      }
    },
    []
  );

  const deleteCase = useCallback(async (caseId: string) => {
    try {
      await featuredCasesApi.adminDeleteCase(caseId);
    } catch (error) {
      console.error("Failed to delete case:", error);
      throw error;
    }
  }, []);

  const upsertConfig = useCallback(
    async (config: {
      source_id: string;
      bbk_id?: string | null;
      case_ids: { case_id: string; sort_order: number }[];
    }) => {
      try {
        await featuredCasesApi.adminUpsertConfig(config);
      } catch (error) {
        console.error("Failed to upsert config:", error);
        throw error;
      }
    },
    []
  );

  const deleteConfig = useCallback(
    async (sourceId: string, bbkId?: string | null) => {
      try {
        await featuredCasesApi.adminDeleteConfig(sourceId, bbkId);
      } catch (error) {
        console.error("Failed to delete config:", error);
        throw error;
      }
    },
    []
  );

  const getConfigDetail = useCallback(
    async (sourceId: string, bbkId?: string | null) => {
      try {
        return await featuredCasesApi.adminGetConfigDetail(sourceId, bbkId);
      } catch (error) {
        console.error("Failed to get config detail:", error);
        throw error;
      }
    },
    []
  );

  return {
    cases,
    casesLoading,
    casesTotal,
    configs,
    configsLoading,
    configsTotal,
    loadCases,
    loadConfigs,
    createCase,
    updateCase,
    deleteCase,
    upsertConfig,
    deleteConfig,
    getConfigDetail,
  };
}
