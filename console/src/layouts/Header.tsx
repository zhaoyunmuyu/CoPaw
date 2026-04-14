import { Layout, Space, Select } from "antd";
// ==================== 语言/主题切换暂时隐藏 (Kun He) ====================
// import LanguageSwitcher from "../components/LanguageSwitcher/index";
// import ThemeToggleButton from "../components/ThemeToggleButton";
// ==================== 语言/主题切换暂时隐藏结束 ====================
import styles from "./index.module.less";
import { useTheme } from "../contexts/ThemeContext";
// ==================== 品牌主题 (Kun He) ====================
import { useBrandTheme } from "../contexts/BrandThemeContext";
// ==================== 品牌主题结束 ====================
// ==================== 超管用户切换 (Kun He) ====================
import { useState, useEffect } from "react";
import { useIframeStore } from "../stores/iframeStore";
import {
  mockFetchUserList,
  type UserInfo,
} from "../api/modules/customerInfo";
// ==================== 超管用户切换结束 ====================

const { Header: AntHeader } = Layout;

export default function Header() {
  const { isDark } = useTheme();
  // ==================== 品牌主题 (Kun He) ====================
  // 获取动态品牌配置，用于显示正确的 logo
  const { theme: brandTheme } = useBrandTheme();
  // ==================== 品牌主题结束 ====================

  // ==================== 超管用户切换 (Kun He) ====================
  // 获取 isSuperManager 和 userId
  const isSuperManager = useIframeStore((state) => state.isSuperManager);
  const userId = useIframeStore((state) => state.userId);
  const setContext = useIframeStore((state) => state.setContext);

  // 用户列表状态
  const [userList, setUserList] = useState<UserInfo[]>([]);
  const [loading, setLoading] = useState(false);

  // 加载用户列表
  useEffect(() => {
    if (isSuperManager) {
      setLoading(true);
      mockFetchUserList()
        .then((res) => {
          if (res?.success && res.data) {
            setUserList(res.data);
          }
        })
        .catch((err) => {
          console.error("[Header] Failed to fetch user list:", err);
        })
        .finally(() => {
          setLoading(false);
        });
    }
  }, [isSuperManager]);

  // 处理用户切换
  const handleUserChange = (newUserId: string) => {
    const selectedUser = userList.find((u) => u.userId === newUserId);
    if (selectedUser) {
      console.info("[Header] Switching to user:", selectedUser);

      // 更新 store 中的用户信息
      setContext({
        userId: selectedUser.userId,
        clawName: selectedUser.clawName ?? null,
        space: selectedUser.space ?? null,
      });

      // 刷新页面以重新加载对话信息
      window.location.reload();
    }
  };
  // ==================== 超管用户切换结束 ====================

  return (
    <>
      <AntHeader className={styles.header}>
        <div className={styles.logoWrapper}>
          {/* ==================== 品牌主题 (Kun He) ==================== */}
          {/* 使用动态品牌 logo，根据 source 和明暗主题切换 */}
          <img
            src={
              isDark
                ? `${import.meta.env.BASE_URL}${brandTheme.darkLogo.replace(/^\//, "")}`
                : `${import.meta.env.BASE_URL}${brandTheme.logo.replace(/^\//, "")}`
            }
            alt={brandTheme.brandName}
            className={styles.logoImg}
          />
          {/* ==================== 品牌主题结束 ==================== */}
          {/* ==================== 超管用户切换 (Kun He) ==================== */}
          {/* 当 isSuperManager 为 true 时，显示用户选择下拉框 */}
          {isSuperManager && (
            <Select
              value={userId}
              onChange={handleUserChange}
              loading={loading}
              style={{ minWidth: 150, marginLeft: 16 }}
              placeholder="选择用户"
              options={userList.map((user) => ({
                label: `${user.clawName || user.userId}`,
                value: user.userId,
              }))}
            />
          )}
          {/* ==================== 超管用户切换结束 ==================== */}
        </div>
        <Space size="middle">
          {/* ==================== 语言/主题切换暂时隐藏 (Kun He) ==================== */}
          {/* <LanguageSwitcher /> */}
          {/* <ThemeToggleButton /> */}
          {/* ==================== 语言/主题切换暂时隐藏结束 ==================== */}
        </Space>
      </AntHeader>
    </>
  );
}
