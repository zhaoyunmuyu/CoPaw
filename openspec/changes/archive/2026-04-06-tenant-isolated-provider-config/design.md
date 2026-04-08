## Context

当前 `ProviderManager` 是一个全局单例，在应用启动时初始化，使用固定路径 `~/.swe.secret/providers/` 存储所有 provider 配置。这在多租户架构中造成了严重问题：

1. **存储路径问题**: `ProviderManager.__init__()` 中 `self.root_path = SECRET_DIR / "providers"` 是全局共享的
2. **API 密钥泄露风险**: 所有租户共享同一个目录，理论上可以互相访问配置
3. **活跃模型冲突**: 租户 A 切换模型会影响租户 B 的模型选择
4. **缺少自动初始化**: 新租户首次访问时没有自动创建默认配置

租户隔离架构已经通过 `TenantIdentityMiddleware` 和 `TenantWorkspaceMiddleware` 实现了租户上下文传递，但 `ProviderManager` 尚未适配这个架构。

## Goals / Non-Goals

**Goals:**
- Provider 配置按租户完全隔离存储
- 每个租户拥有独立的 API 密钥、base URL 配置
- 每个租户拥有独立的活跃模型选择
- 向后兼容：单租户部署使用 "default" 租户
- 自动初始化：新租户首次访问时自动复制 default 配置

**Non-Goals:**
- 不修改 Provider 协议或模型调用方式
- 不修改 `TenantModelConfig` 的数据结构（已正确隔离）
- 不引入新的 provider 类型
- 不修改多租户以外的其他功能

## Decisions

### 决策 1: 在 ProviderManager 中添加租户上下文支持

**选择**: 修改 `ProviderManager` 支持动态租户路径，而非创建新类

**理由**:
- 保持现有代码兼容性，最小化改动范围
- `ProviderManager` 的逻辑（如模型发现、连接测试）是通用的，只需改变存储位置
- 可以通过 `get_instance(tenant_id)` 方式获取租户特定实例

**替代方案**:
- 创建 `TenantProviderManager` 包装类：会增加一层抽象，复杂度更高
- 完全重写：风险太大，现有功能需要重新测试

### 决策 2: 使用 "default" 租户作为配置模板

**选择**: 新租户首次访问时，从 "default" 租户复制配置

**理由**:
- 与现有 `TenantModelManager` 的回退逻辑保持一致
- 单租户部署自然使用 "default" 租户
- 管理员可以预设 default 配置作为模板

**替代方案**:
- 从全局配置迁移：需要维护两套配置，复杂度高
- 创建空配置：用户体验差，需要手动配置每个新租户

### 决策 3: 在 TenantWorkspaceMiddleware 中初始化租户 Provider 配置

**选择**: 中间件负责确保租户配置存在，按需从 default 复制

**理由**:
- 集中处理租户初始化逻辑
- 利用现有的请求上下文机制
- 可以异步处理，不阻塞请求

**替代方案**:
- 在 ProviderManager 内部处理：会增加单例复杂度
- 单独的初始化 API：需要客户端调用，体验差

### 决策 4: 保留 ProviderManager 单例模式，但按租户缓存实例

**选择**: `ProviderManager.get_instance(tenant_id)` 返回租户特定实例，内部按租户缓存

**理由**:
- 保持向后兼容：无参数调用返回 default 租户实例
- 避免频繁创建/销毁实例的开销
- 每个租户实例独立，互不干扰

**数据结构**:
```python
class ProviderManager:
    _instances: dict[str, ProviderManager] = {}  # tenant_id -> instance

    @staticmethod
    def get_instance(tenant_id: str | None = None) -> ProviderManager:
        tenant_id = tenant_id or "default"
        if tenant_id not in ProviderManager._instances:
            ProviderManager._instances[tenant_id] = ProviderManager(tenant_id)
        return ProviderManager._instances[tenant_id]
```

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|---------|
| [风险] 现有单例调用处需要修改 | 保持无参数调用向后兼容，返回 default 租户实例 |
| [风险] 配置迁移失败导致数据丢失 | 迁移脚本先备份原配置，失败时可回滚 |
| [风险] 租户实例过多导致内存占用 | 实现 LRU 缓存，限制实例数量 |
| [风险] 并发创建同一租户实例出现竞争 | 使用线程锁保护 `_instances` 字典操作 |
| [风险] 文件系统权限问题 | 保持现有权限设置逻辑 (0o700)，每个租户目录独立设置 |

## Migration Plan

### 阶段 1: 自动迁移（部署时执行）

```python
# scripts/migrate_provider_config.py
def migrate_to_tenant_isolated():
    # 1. 检查旧配置是否存在
    old_providers_dir = SECRET_DIR / "providers"
    if not old_providers_dir.exists():
        return  # 无需迁移

    # 2. 创建 default 租户目录
    default_tenant_dir = SECRET_DIR / "default" / "providers"
    default_tenant_dir.mkdir(parents=True, exist_ok=True)

    # 3. 复制所有配置到 default 租户
    for item in old_providers_dir.iterdir():
        target = default_tenant_dir / item.name
        if item.is_file():
            shutil.copy2(item, target)
        elif item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)

    # 4. 备份旧配置
    backup_dir = SECRET_DIR / "providers.backup.{timestamp}"
    shutil.move(str(old_providers_dir), str(backup_dir))
```

### 阶段 2: 运行时自动初始化

在 `TenantWorkspaceMiddleware.dispatch()` 中添加：
```python
# 确保租户 provider 配置存在
await self._ensure_tenant_provider_config(tenant_id)

async def _ensure_tenant_provider_config(self, tenant_id: str):
    """确保租户 provider 配置存在，不存在则从 default 复制。"""
    tenant_providers_dir = SECRET_DIR / tenant_id / "providers"
    if tenant_providers_dir.exists():
        return

    # 从 default 租户复制
    default_dir = SECRET_DIR / "default" / "providers"
    if default_dir.exists():
        shutil.copytree(default_dir, tenant_providers_dir)
    else:
        # 创建空目录结构
        tenant_providers_dir.mkdir(parents=True, exist_ok=True)
        (tenant_providers_dir / "builtin").mkdir(exist_ok=True)
        (tenant_providers_dir / "custom").mkdir(exist_ok=True)
```

### 回滚策略

1. 恢复备份目录：`mv providers.backup.{timestamp} providers`
2. 代码回滚到上一版本
3. 重启应用

## Open Questions

1. **问题**: 是否需要支持跨租户 provider 共享（如共享的 API 密钥）？
   - **初步想法**: 不支持，每个租户完全独立，符合多租户安全原则

2. **问题**: 租户配置过多时的性能考虑？
   - **初步想法**: 使用 LRU 缓存限制内存中实例数量，惰性加载

3. **问题**: CLI 命令如何支持多租户？
   - **初步想法**: 添加 `--tenant-id` 参数，默认使用 "default"
