/**
 * Cases API types
 */

export interface CaseStep {
  title: string;
  content: string;
}

export interface CaseDetail {
  iframe_url: string;
  iframe_title: string;
  steps: CaseStep[];
}

export interface Case {
  id: string;
  label: string;
  value: string;
  image_url?: string;
  sort_order: number;
  is_active?: boolean;
  detail?: CaseDetail;
}

export interface UserCasesMapping {
  user_cases: Record<string, string[]>;
}