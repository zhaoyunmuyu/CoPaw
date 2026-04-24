import { useState, useCallback } from "react";
import { featuredCasesApi } from "@/api/modules/featuredCases";
import type { FeaturedCase, FeaturedCaseCreate } from "@/api/types/featuredCases";

export function useFeaturedCases() {
  const [cases, setCases] = useState<FeaturedCase[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);

  const loadCases = useCallback(
    async (params?: { bbk_id?: string; page?: number; page_size?: number }) => {
      setLoading(true);
      try {
        const data = await featuredCasesApi.adminListCases(params);
        setCases(data.cases);
        setTotal(data.total);
      } catch (error) {
        console.error("Failed to load cases:", error);
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const createCase = useCallback(async (caseItem: FeaturedCaseCreate) => {
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

  return {
    cases,
    loading,
    total,
    loadCases,
    createCase,
    updateCase,
    deleteCase,
  };
}