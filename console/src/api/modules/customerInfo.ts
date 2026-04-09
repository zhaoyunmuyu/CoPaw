/**
 * ============================================================
 * 客户信息查询 API
 * Author: Kun He
 * Date: 2026-04-07
 * ============================================================
 *
 * 用于查询真实客户信息，在内嵌模式下调用
 * 当 iframe 内嵌且 URL 参数 origin === "Y" 时触发
 *
 * ============================================================
 */

import { agentApi } from "./agent";

export interface CustomerInfoRequest {
  inputParams: {
    userId: string,
    sysId: string,
    bbk: string,
    orgCode: string,
    orgLvl: string,
    positionId: string,
  }
}

/**
 * 客户信息数据
 */
export interface CustomerInfoData {
  userChange: boolean;
  sysId: string;
  token: string;
  bbk: string;
  orgCode: string;
  orgLvl: string;
  userId: string;
  positionId: string;
}

/**
 * 客户信息查询响应
 */
export interface CustomerInfoResponse {
  /** 返回码，SUC0000 表示成功 */
  returnCode: string;
  errorMsg?: string;
  body: {
    output: {
      result: CustomerInfoData
    }
  }
}

/**
 * 用户初始化请求参数
 */
export interface UserInitRequest {
  filename: string;
  text: string;
}

/**
 * 用户初始化响应
 */
export interface UserInitResponse {
  /** 是否成功 */
  success: boolean;
  /** 返回消息 */
  message?: string;
  /** 初始化数据（存储到 localStorage） */
  data?: Record<string, unknown>;
}

/**
 * 检查用户是否已初始化
 * @param userId - 用户 ID
 * @returns 是否已初始化
 */
export function isUserInitialized(userId: string): boolean {
  const key = `swe-${userId}`;
  return localStorage.getItem(key) === "exist";
}

/**
 * 设置用户已初始化标记
 * @param userId - 用户 ID
 */
export function setUserInitialized(userId: string): void {
  const key = `swe-${userId}`;
  localStorage.setItem(key, "exist");
}

/**
 * 用户初始化 API
 *
 * @param request - 请求参数
 * @returns 初始化响应
 */
export async function fetchUserInit(
  req: UserInitRequest,
): Promise<{ success: boolean } | null> {
  try {
    const response = await agentApi.agentInit({
      filename: req.filename,
      text: req.text,
    });

    return response ? { success: response.success } : null;
  } catch (error) {
    console.error("[UserInit] API request error:", error);
    return null;
  }
}

/**
 * 查询客户信息 API
 *
 * @param request - 请求参数
 * @returns 客户信息响应
 */
export async function fetchCustomerInfo(
  request: CustomerInfoRequest,
): Promise<CustomerInfoResponse | null> {
  try {
    const baseUrl = window.__env__.baseUrl || ""
    const isDev = baseUrl === 'yourapi'
    const env = isDev ? 'dev' : 'prd'
    // TODO: 替换为真实的 API Key
    const apiKey = isDev ? 'xxxx' : 'your-api-key'
    // TODO: 替换为真实的 API 地址
    const apiUrl = `${baseUrl}/openapi/${env}/yourapi`
    const response = await fetch(apiUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "api-key": apiKey
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      console.error("[CustomerInfo] API request failed:", response.status);
      return null;
    }

    const result: CustomerInfoResponse = await response.json();
    return result;
  } catch (error) {
    console.error("[CustomerInfo] API request error:", error);
    return null;
  }
}


/** Mock 延迟时间（毫秒） */
const MOCK_DELAY = 500;

/**
 * 用户信息
 */
export interface UserInfo {
  /** 用户 ID */
  userId: string;
  /** 用户名称 */
  clawName?: string;
  /** 空间标识 */
  space?: string;
}

/**
 * 用户列表响应
 */
export interface UserListResponse {
  /** 是否成功 */
  success: boolean;
  /** 返回消息 */
  message?: string;
  /** 用户列表 */
  data?: UserInfo[];
}

/**
 * 获取用户列表 API
 *
 * @returns 用户列表响应
 */
export async function fetchUserList(): Promise<UserListResponse | null> {
  try {
    // TODO: 替换为真实的 API 地址
    const apiUrl = "/api/user/list";

    const response = await fetch(apiUrl, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      console.error("[UserList] API request failed:", response.status);
      return null;
    }

    const result: UserListResponse = await response.json();
    return result;
  } catch (error) {
    console.error("[UserList] API request error:", error);
    return null;
  }
}

/**
 * Mock 用户列表数据
 */
const MOCK_USER_LIST: UserInfo[] = [
  { userId: "80000001", clawName: "张三", space: "default" },
  { userId: "80000002", clawName: "李四", space: "default" },
  { userId: "80000003", clawName: "王五", space: "default" },
  { userId: "80000004", clawName: "赵六", space: "default" },
  { userId: "80000005", clawName: "钱七", space: "default" },
];

/**
 * Mock 获取用户列表 API
 *
 * @returns 用户列表响应
 */
export async function mockFetchUserList(): Promise<UserListResponse> {
  // 模拟网络延迟
  await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY));

  console.info("[UserList] Mock API called");

  return {
    success: true,
    message: "User list fetched successfully",
    data: MOCK_USER_LIST,
  };
}