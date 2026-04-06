## 1. ProviderManager 租户隔离改造

- [x] 1.1 修改 `ProviderManager.__init__` 支持租户 ID 参数和动态路径
- [x] 1.2 实现 `ProviderManager.get_instance(tenant_id)` 多例缓存机制
- [x] 1.3 添加线程安全的实例缓存（使用锁保护 `_instances` 字典）
- [x] 1.4 修改所有存储路径相关方法（`_save_provider`, `load_provider`, `save_active_model`, `load_active_model`）
- [x] 1.5 添加 `get_tenant_root_path(tenant_id)` 辅助方法
- [x] 1.6 确保向后兼容：无参数调用返回 default 租户实例
- [x] 1.7 更新 `ProviderManager` 单元测试

## 2. 租户配置自动初始化

- [x] 2.1 在 `TenantWorkspaceMiddleware` 中添加 `_ensure_tenant_provider_config` 方法
- [x] 2.2 实现从 default 租户复制配置的逻辑
- [x] 2.3 实现创建空目录结构的回退逻辑
- [x] 2.4 添加配置初始化的日志记录
- [x] 2.5 处理并发初始化竞争（文件锁或幂等操作）
- [x] 2.6 更新 `TenantWorkspaceMiddleware` 单元测试

## 3. 模型工厂适配

- [x] 3.1 修改 `create_model_and_formatter` 从租户上下文获取 ProviderManager
- [x] 3.2 更新 `model_factory.py` 中的租户配置获取逻辑
- [x] 3.3 确保在没有租户上下文时使用 default 租户（向后兼容）
- [x] 3.4 更新 `model_factory` 单元测试

## 4. API 层适配

- [x] 4.1 修改 `providers.py` 路由处理器使用租户特定的 ProviderManager
- [x] 4.2 更新所有 provider API 端点以获取当前租户 ID
- [x] 4.3 确保 API 在缺少租户上下文时返回适当的错误（400 Bad Request）
- [x] 4.4 更新 provider API 集成测试

## 5. CLI 适配

- [x] 5.1 在 `providers_cmd.py` 中添加 `--tenant-id` 参数支持
- [x] 5.2 修改所有 CLI 命令使用租户特定的 ProviderManager
- [x] 5.3 默认使用 "default" 租户（向后兼容）
- [x] 5.4 更新 CLI 命令的帮助文档
- [x] 5.5 更新 CLI 测试

## 6. 数据迁移

- [x] 6.1 创建 `scripts/migrate_provider_config.py` 迁移脚本
- [x] 6.2 实现从全局目录到 default 租户目录的复制逻辑
- [x] 6.3 实现迁移前的备份机制
- [x] 6.4 实现幂等性检查（避免重复迁移）
- [x] 6.5 添加迁移脚本的日志输出
- [x] 6.6 测试迁移脚本（正常情况和边界情况）

## 7. 集成与端到端测试

- [x] 7.1 创建租户隔离的集成测试（多租户配置互不干扰）
- [x] 7.2 测试自动初始化逻辑（新租户首次访问）
- [x] 7.3 测试迁移后的系统行为
- [x] 7.4 测试向后兼容（单租户模式）
- [x] 7.5 性能测试（多租户并发访问）

## 8. 文档更新

- [x] 8.1 更新 CLAUDE.md 中的多租户架构说明
- [x] 8.2 添加 Provider 配置隔离的开发者文档
- [x] 8.3 更新 CLI 帮助文档
- [x] 8.4 创建迁移指南（Migration Guide）

## 9. 部署与验证

- [ ] 9.1 在测试环境运行迁移脚本
- [ ] 9.2 验证所有租户配置正确隔离
- [ ] 9.3 验证 API 密钥隔离有效
- [ ] 9.4 验证新租户自动初始化工作正常
