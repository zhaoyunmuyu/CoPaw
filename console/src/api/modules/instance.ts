import { request } from "../request";

// Types
export interface Source {
  source_id: string;
  source_name: string;
  created_at?: string;
}

export interface SourceWithStats extends Source {
  total_instances: number;
  total_users: number;
  active_instances: number;
}

export interface Instance {
  instance_id: string;
  source_id: string;
  bbk_id?: string;
  instance_name: string;
  instance_url: string;
  max_users: number;
  status: "active" | "inactive";
  created_at?: string;
}

export interface InstanceWithUsage extends Instance {
  current_users: number;
  usage_percent: number;
  warning_level: "normal" | "warning" | "critical";
  source_name?: string;
  bbk_name?: string;
}

export interface UserAllocation {
  id?: number;
  user_id: string;
  source_id: string;
  instance_id: string;
  allocated_at?: string;
  status: "active" | "migrated";
  source_name?: string;
  instance_name?: string;
  instance_url?: string;
}

export interface OperationLog {
  id?: number;
  action: string;
  target_type: string;
  target_id: string;
  old_value?: Record<string, unknown>;
  new_value?: Record<string, unknown>;
  operator?: string;
  created_at?: string;
}

export interface OverviewStats {
  total_instances: number;
  total_users: number;
  active_instances: number;
  warning_instances: number;
  critical_instances: number;
}

export interface AllocateUserRequest {
  user_id: string;
  source_id: string;
  instance_id?: string;
}

export interface AllocateUserResponse {
  success: boolean;
  user_id: string;
  source_id?: string;
  instance_id?: string;
  instance_name?: string;
  instance_url?: string;
  message?: string;
}

// API functions
export const instanceApi = {
  // Overview
  getOverview: async (): Promise<OverviewStats> => {
    return request("/instance/overview");
  },

  // Sources
  getSources: async (): Promise<{
    sources: SourceWithStats[];
    total: number;
  }> => {
    return request("/instance/sources");
  },

  // Instances
  getInstances: async (filters?: {
    source_id?: string;
    status?: string;
  }): Promise<{ instances: InstanceWithUsage[]; total: number }> => {
    const params = new URLSearchParams();
    if (filters) {
      Object.entries(filters).forEach(([key, value]) => {
        if (value !== undefined && value !== null) params.append(key, value);
      });
    }
    const query = params.toString() ? `?${params.toString()}` : "";
    return request(`/instance/instances${query}`);
  },

  getInstance: async (instanceId: string): Promise<InstanceWithUsage> => {
    return request(`/instance/instances/${instanceId}`);
  },

  createInstance: async (data: {
    instance_id: string;
    source_id: string;
    bbk_id?: string;
    instance_name: string;
    instance_url: string;
    max_users?: number;
  }): Promise<{ success: boolean; data: Instance }> => {
    return request("/instance/instances", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  updateInstance: async (
    instanceId: string,
    data: {
      instance_name?: string;
      instance_url?: string;
      max_users?: number;
      status?: string;
    },
  ): Promise<{ success: boolean; data: Instance }> => {
    return request(`/instance/instances/${instanceId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },

  deleteInstance: async (instanceId: string): Promise<{ success: boolean }> => {
    return request(`/instance/instances/${instanceId}`, { method: "DELETE" });
  },

  // Allocations
  getUserIds: async (): Promise<string[]> => {
    return request("/instance/user-ids");
  },

  getAllocations: async (params?: {
    user_id?: string;
    source_id?: string;
    instance_id?: string;
    page?: number;
    page_size?: number;
  }): Promise<{ allocations: UserAllocation[]; total: number }> => {
    const searchParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null)
          searchParams.append(key, String(value));
      });
    }
    const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
    return request(`/instance/allocations${query}`);
  },

  getUserInstanceUrl: async (
    userId: string,
    sourceId: string,
  ): Promise<AllocateUserResponse> => {
    const params = new URLSearchParams();
    params.append("user_id", userId);
    params.append("source_id", sourceId);
    return request(`/instance/allocations/url?${params.toString()}`);
  },

  allocateUser: async (
    data: AllocateUserRequest,
  ): Promise<AllocateUserResponse> => {
    return request("/instance/allocations", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  migrateUser: async (data: {
    user_id: string;
    source_id: string;
    target_instance_id: string;
  }): Promise<AllocateUserResponse> => {
    return request("/instance/allocations/migrate", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  deleteAllocation: async (
    userId: string,
    sourceId: string,
  ): Promise<{ success: boolean }> => {
    const params = new URLSearchParams();
    params.append("user_id", userId);
    params.append("source_id", sourceId);
    return request(`/instance/allocations?${params.toString()}`, {
      method: "DELETE",
    });
  },

  // Logs
  getLogs: async (params?: {
    action?: string;
    target_type?: string;
    target_id?: string;
    page?: number;
    page_size?: number;
  }): Promise<{ logs: OperationLog[]; total: number }> => {
    const searchParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null)
          searchParams.append(key, String(value));
      });
    }
    const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
    return request(`/instance/logs${query}`);
  },
};
