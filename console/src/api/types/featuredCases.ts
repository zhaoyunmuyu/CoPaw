/**
 * Featured Cases API types (simplified - merged tables)
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
  source_id: string; // From X-Source-Id header
  bbk_id?: string | null;
  case_id: string;
  label: string;
  value: string;
  image_url?: string;
  iframe_url?: string;
  iframe_title?: string;
  steps?: CaseStep[];
  sort_order: number;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface FeaturedCaseCreate {
  // source_id NOT included - comes from X-Source-Id header
  bbk_id?: string | null;
  case_id: string;
  label: string;
  value: string;
  image_url?: string;
  iframe_url?: string;
  iframe_title?: string;
  steps?: CaseStep[];
  sort_order?: number;
}

export interface FeaturedCaseUpdate {
  bbk_id?: string | null;
  label?: string;
  value?: string;
  image_url?: string;
  iframe_url?: string;
  iframe_title?: string;
  steps?: CaseStep[];
  sort_order?: number;
  is_active?: boolean;
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