import { request } from "../request";
import type { Case, UserCasesMapping } from "../types/cases";

export const casesApi = {
  /** Get case list for current user (filtered by userId) */
  listCases: () => request<Case[]>("/cases"),

  /** Get case detail by ID */
  getCaseDetail: (caseId: string) =>
    request<Case>(`/cases/${encodeURIComponent(caseId)}`),

  /** Create a new case (admin) */
  createCase: (caseItem: Case) =>
    request<Case>("/cases", {
      method: "POST",
      body: JSON.stringify(caseItem),
    }),

  /** Update an existing case (admin) */
  updateCase: (caseId: string, caseItem: Case) =>
    request<Case>(`/cases/${encodeURIComponent(caseId)}`, {
      method: "PUT",
      body: JSON.stringify(caseItem),
    }),

  /** Delete a case (admin) */
  deleteCase: (caseId: string) =>
    request<{ deleted: string }>(`/cases/${encodeURIComponent(caseId)}`, {
      method: "DELETE",
    }),

  /** Get all cases including inactive (admin) */
  listAllCases: () => request<Case[]>("/cases/admin/all"),

  /** Get user-case mapping (admin) */
  getUserMapping: () => request<UserCasesMapping>("/cases/admin/user-mapping"),

  /** Update user-case mapping (admin) */
  updateUserMapping: (mapping: Record<string, string[]>) =>
    request<{ success: boolean }>("/cases/admin/user-mapping", {
      method: "PUT",
      body: JSON.stringify({ user_cases: mapping }),
    }),
};