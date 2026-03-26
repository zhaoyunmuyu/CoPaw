import { request } from "../request";

// Types
export interface OverviewStats {
  online_users: number;
  total_users: number;
  model_distribution: ModelUsage[];
  total_tokens: number;
  input_tokens: number;
  output_tokens: number;
  total_sessions: number;
  total_conversations: number;
  avg_duration_ms: number;
  top_tools: ToolUsage[];
  top_skills: SkillUsage[];
  daily_trend: DailyStats[];
}

export interface ModelUsage {
  model_name: string;
  count: number;
  total_tokens: number;
  input_tokens: number;
  output_tokens: number;
}

export interface ToolUsage {
  tool_name: string;
  count: number;
  avg_duration_ms: number;
  error_count: number;
}

export interface SkillUsage {
  skill_name: string;
  count: number;
}

export interface DailyStats {
  date: string;
  total_users: number;
  active_users: number;
  total_tokens: number;
  session_count: number;
}

export interface UserStats {
  user_id: string;
  model_usage: ModelUsage[];
  total_tokens: number;
  input_tokens: number;
  output_tokens: number;
  total_sessions: number;
  total_conversations: number;
  avg_duration_ms: number;
  tools_used: ToolUsage[];
  skills_used: SkillUsage[];
}

export interface UserListItem {
  user_id: string;
  total_sessions: number;
  total_conversations: number;
  total_tokens: number;
  last_active: string | null;
}

export interface TraceListItem {
  trace_id: string;
  user_id: string;
  session_id: string;
  channel: string;
  start_time: string;
  duration_ms: number | null;
  total_tokens: number;
  model_name: string | null;
  status: string;
  tools_count: number;
}

export interface TraceDetail {
  trace: Trace;
  spans: Span[];
  llm_duration_ms: number;
  tool_duration_ms: number;
  tools_called: ToolCall[];
}

export interface Trace {
  trace_id: string;
  user_id: string;
  session_id: string;
  channel: string;
  start_time: string;
  end_time: string | null;
  duration_ms: number | null;
  model_name: string | null;
  total_input_tokens: number;
  total_output_tokens: number;
  tools_used: string[];
  skills_used: string[];
  status: string;
  error: string | null;
}

export interface Span {
  span_id: string;
  trace_id: string;
  name: string;
  event_type: string;
  start_time: string;
  end_time: string | null;
  duration_ms: number | null;
  model_name: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  tool_name: string | null;
  skill_name: string | null;
  tool_input: Record<string, unknown> | null;
  tool_output: string | null;
  error: string | null;
}

export interface ToolCall {
  tool_name: string;
  tool_input: Record<string, unknown> | null;
  tool_output: string | null;
  duration_ms: number | null;
  error: string | null;
}

// API functions
export const tracingApi = {
  getOverview: async (startDate?: string, endDate?: string): Promise<OverviewStats> => {
    const params = new URLSearchParams();
    if (startDate) params.append("start_date", startDate);
    if (endDate) params.append("end_date", endDate);
    return request(`/tracing/overview?${params.toString()}`);
  },

  getUsers: async (
    page = 1,
    pageSize = 20,
    userId?: string
  ): Promise<{ items: UserListItem[]; total: number; page: number; page_size: number }> => {
    const params = new URLSearchParams();
    params.append("page", page.toString());
    params.append("page_size", pageSize.toString());
    if (userId) params.append("user_id", userId);
    return request(`/tracing/users?${params.toString()}`);
  },

  getUserStats: async (userId: string, startDate?: string, endDate?: string): Promise<UserStats> => {
    const params = new URLSearchParams();
    if (startDate) params.append("start_date", startDate);
    if (endDate) params.append("end_date", endDate);
    const query = params.toString() ? `?${params.toString()}` : "";
    return request(`/tracing/users/${encodeURIComponent(userId)}${query}`);
  },

  getTraces: async (
    page = 1,
    pageSize = 20,
    filters?: {
      user_id?: string;
      session_id?: string;
      status?: string;
      start_date?: string;
      end_date?: string;
    }
  ): Promise<{ items: TraceListItem[]; total: number; page: number; page_size: number }> => {
    const params = new URLSearchParams();
    params.append("page", page.toString());
    params.append("page_size", pageSize.toString());
    if (filters) {
      Object.entries(filters).forEach(([key, value]) => {
        if (value) params.append(key, value);
      });
    }
    return request(`/tracing/traces?${params.toString()}`);
  },

  getTraceDetail: async (traceId: string): Promise<TraceDetail> => {
    return request(`/tracing/traces/${traceId}`);
  },

  getModelUsage: async (startDate?: string, endDate?: string): Promise<{ models: ModelUsage[] }> => {
    const params = new URLSearchParams();
    if (startDate) params.append("start_date", startDate);
    if (endDate) params.append("end_date", endDate);
    const query = params.toString() ? `?${params.toString()}` : "";
    return request(`/tracing/models${query}`);
  },

  getToolUsage: async (startDate?: string, endDate?: string): Promise<{ tools: ToolUsage[] }> => {
    const params = new URLSearchParams();
    if (startDate) params.append("start_date", startDate);
    if (endDate) params.append("end_date", endDate);
    const query = params.toString() ? `?${params.toString()}` : "";
    return request(`/tracing/tools${query}`);
  },
};
