/**
 * Greeting API types
 */

export interface GreetingConfig {
  id: number;
  source_id: string;
  bbk_id: string | null;
  greeting: string;
  subtitle?: string;
  placeholder?: string;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface GreetingConfigCreate {
  source_id: string;
  bbk_id?: string | null;
  greeting: string;
  subtitle?: string;
  placeholder?: string;
}

export interface GreetingConfigUpdate {
  greeting?: string;
  subtitle?: string;
  placeholder?: string;
  is_active?: boolean;
}

export interface GreetingDisplay {
  greeting: string;
  subtitle?: string;
  placeholder?: string;
}

export interface GreetingConfigListResponse {
  configs: GreetingConfig[];
  total: number;
}
