/**
 * Featured Cases API types
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

export interface FeaturedCase {
  id: number;
  case_id: string;
  label: string;
  value: string;
  image_url?: string;
  iframe_url?: string;
  iframe_title?: string;
  steps?: CaseStep[];
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface FeaturedCaseCreate {
  case_id: string;
  label: string;
  value: string;
  image_url?: string;
  iframe_url?: string;
  iframe_title?: string;
  steps?: CaseStep[];
}

export interface FeaturedCaseUpdate {
  label?: string;
  value?: string;
  image_url?: string;
  iframe_url?: string;
  iframe_title?: string;
  steps?: CaseStep[];
  is_active?: boolean;
}

export interface CaseConfigItem {
  case_id: string;
  sort_order: number;
}

export interface CaseConfigCreate {
  source_id: string;
  bbk_id?: string | null;
  case_ids: CaseConfigItem[];
}

export interface CaseConfigListItem {
  source_id: string;
  bbk_id: string | null;
  case_count: number;
}

export interface CaseConfigListResponse {
  configs: CaseConfigListItem[];
  total: number;
}

export interface CaseConfigDetail {
  source_id: string;
  bbk_id: string | null;
  case_ids: string[];
}

export interface FeaturedCaseListResponse {
  cases: FeaturedCase[];
  total: number;
}

// Display format (from /featured-cases endpoint)
export interface FeaturedCaseDisplay {
  id: string;
  label: string;
  value: string;
  image_url?: string;
  sort_order: number;
  detail?: CaseDetail;
}
