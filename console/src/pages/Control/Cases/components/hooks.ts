import { useState, useCallback } from "react";
import { casesApi } from "@/api/modules/cases";
import type { Case } from "@/api/types/cases";

export function useCases() {
  const [cases, setCases] = useState<Case[]>([]);
  const [loading, setLoading] = useState(false);
  const [userMapping, setUserMapping] = useState<Record<string, string[]>>({});

  const loadCases = useCallback(async () => {
    setLoading(true);
    try {
      const data = await casesApi.listAllCases();
      setCases(data);
    } catch (error) {
      console.error("Failed to load cases:", error);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadUserMapping = useCallback(async () => {
    try {
      const data = await casesApi.getUserMapping();
      setUserMapping(data.user_cases || {});
    } catch (error) {
      console.error("Failed to load user mapping:", error);
    }
  }, []);

  const createCase = useCallback(async (caseItem: Case) => {
    try {
      const created = await casesApi.createCase(caseItem);
      setCases((prev) => [...prev, created]);
      return true;
    } catch (error) {
      console.error("Failed to create case:", error);
      throw error;
    }
  }, []);

  const updateCase = useCallback(async (caseId: string, caseItem: Case) => {
    try {
      const updated = await casesApi.updateCase(caseId, caseItem);
      setCases((prev) =>
        prev.map((c) => (c.id === caseId ? updated : c)),
      );
      return true;
    } catch (error) {
      console.error("Failed to update case:", error);
      throw error;
    }
  }, []);

  const deleteCase = useCallback(async (caseId: string) => {
    try {
      await casesApi.deleteCase(caseId);
      setCases((prev) => prev.filter((c) => c.id !== caseId));
      return true;
    } catch (error) {
      console.error("Failed to delete case:", error);
      throw error;
    }
  }, []);

  const updateUserMapping = useCallback(
    async (mapping: Record<string, string[]>) => {
      try {
        await casesApi.updateUserMapping(mapping);
        setUserMapping(mapping);
        return true;
      } catch (error) {
        console.error("Failed to update user mapping:", error);
        throw error;
      }
    },
    [],
  );

  return {
    cases,
    loading,
    userMapping,
    loadCases,
    loadUserMapping,
    createCase,
    updateCase,
    deleteCase,
    updateUserMapping,
  };
}