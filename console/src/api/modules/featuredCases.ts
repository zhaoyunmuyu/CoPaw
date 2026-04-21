/**
 * Featured Cases API module
 */
import { request } from "../request";
import type {
  FeaturedCase,
  FeaturedCaseCreate,
  FeaturedCaseUpdate,
  FeaturedCaseDisplay,
  FeaturedCaseListResponse,
  CaseConfigCreate,
  CaseConfigListResponse,
  CaseConfigDetail,
} from "../types/featuredCases";

export const featuredCasesApi = {
  /** Get cases for current context (from X-Source-Id and X-Bbk-Id headers) */
  listCases: () => request<FeaturedCaseDisplay[]>("/featured-cases"),

  /** Get case detail by ID */
  getCaseDetail: (caseId: string) =>
    request<FeaturedCase>(`/featured-cases/${encodeURIComponent(caseId)}`),

  // ==================== Admin: Case definitions ====================

  /** Admin: list all case definitions */
  adminListCases: (params?: { page?: number; page_size?: number }) => {
    const query = params
      ? new URLSearchParams(
          Object.entries(params)
            .filter(([_, v]) => v !== undefined)
            .map(([k, v]) => [k, String(v)])
        ).toString()
      : "";
    return request<FeaturedCaseListResponse>(
      `/featured-cases/admin/cases${query ? `?${query}` : ""}`
    );
  },

  /** Admin: create case definition */
  adminCreateCase: (caseItem: FeaturedCaseCreate) =>
    request<{ success: boolean; data: FeaturedCase }>(
      "/featured-cases/admin/cases",
      {
        method: "POST",
        body: JSON.stringify(caseItem),
      }
    ),

  /** Admin: update case definition */
  adminUpdateCase: (caseId: string, caseItem: FeaturedCaseUpdate) =>
    request<{ success: boolean; data: FeaturedCase }>(
      `/featured-cases/admin/cases/${encodeURIComponent(caseId)}`,
      {
        method: "PUT",
        body: JSON.stringify(caseItem),
      }
    ),

  /** Admin: delete case definition */
  adminDeleteCase: (caseId: string) =>
    request<{ success: boolean }>(
      `/featured-cases/admin/cases/${encodeURIComponent(caseId)}`,
      {
        method: "DELETE",
      }
    ),

  // ==================== Admin: Case configs ====================

  /** Admin: list case configs */
  adminListConfigs: (params?: {
    source_id?: string;
    page?: number;
    page_size?: number;
  }) => {
    const query = params
      ? new URLSearchParams(
          Object.entries(params)
            .filter(([_, v]) => v !== undefined)
            .map(([k, v]) => [k, String(v)])
        ).toString()
      : "";
    return request<CaseConfigListResponse>(
      `/featured-cases/admin/configs${query ? `?${query}` : ""}`
    );
  },

  /** Admin: get config detail */
  adminGetConfigDetail: (sourceId: string, bbkId?: string | null) => {
    const params = new URLSearchParams({ source_id: sourceId });
    if (bbkId) params.append("bbk_id", bbkId);
    return request<CaseConfigDetail>(
      `/featured-cases/admin/configs/detail?${params.toString()}`
    );
  },

  /** Admin: upsert case config */
  adminUpsertConfig: (config: CaseConfigCreate) =>
    request<{ success: boolean }>("/featured-cases/admin/configs", {
      method: "PUT",
      body: JSON.stringify(config),
    }),

  /** Admin: delete case config */
  adminDeleteConfig: (sourceId: string, bbkId?: string | null) => {
    const params = new URLSearchParams({ source_id: sourceId });
    if (bbkId) params.append("bbk_id", bbkId);
    return request<{ success: boolean }>(
      `/featured-cases/admin/configs?${params.toString()}`,
      {
        method: "DELETE",
      }
    );
  },
};
