# SWE 定时任务运行能力解耦实现计划

> 按用户约定在当前分支主线程顺序实施，不启动子代理，不自动提交、推送或更新行内包。

**Goal:** 通知、心跳、梦境和会话清理不再需要实例化或调用旧 CronManager，外部接口及新旧业务行为不变。

**Architecture:** 从旧管理器机械提取独立通知发送器和系统业务执行器，旧 CronManager 继承这些实现保持旧入口兼容。纯会话裁剪算法单独存放，文件任务清理留在明确的兼容适配器，新版数据库会话清理直接引用纯工具。新业务调用独立服务；旧任务管理、工作区旧管理器生命周期和存量迁移不在本轮删除。

**Tech Stack:** Python、pytest、现有 Workspace/Session/Channel 服务与共享数据库。

**Spec:** 用户已确认：已迁移的是调度管理，本轮只拆除运行能力对旧管理类的依赖，不能重复迁移或改变已有执行、通知、清理和系统配置同步语义。

## Global Constraints

- Scheduler 管调度，SWE 保留业务执行和结果写库；不新增数据库表、配置、外部接口或 HTTP 回执。
- 旧 CronManager 的公开方法、文件任务处理和既有调用保持兼容；不得删除旧任务或改变旧定时器。
- 通知保持渠道、租户来源隔离、推送链接、异常与取消传播；新通知失败不得回退读取旧文件。
- 新版梦境仍不附带归档；旧调用默认行为保持。归档继续不初始化 Agent。
- 会话清理继续包含旧文件任务和新版数据库任务，保留会话锁、清理计数、结果元数据、部分失败和 SQL 历史不删除规则。
- 函数复杂度不超过 15；提取代码不通过复制旧管理器或动态加载其方法达成。

## Task 1：提取独立运行服务（TDD）

Create: `src/swe/app/crons/notification_sender.py`、`system_runtime.py`、`session_cleanup.py`、`legacy_session_cleanup.py`。
Modify: `src/swe/app/crons/manager.py`。
Test: `tests/unit/app/test_cron_business_services.py`，以及原通知、来源绑定、梦境和会话清理用例。

1. 新测试构造访问 cron_manager 即抛错的工作区，验证通知推送、心跳上下文、梦境执行和新旧会话清理能够完成；先运行并观察缺少独立服务或旧依赖导致的失败。
2. 提取 `CronNotificationSender`，接收 channel_manager、agent_id、tenant_id；`SystemTaskRuntime` 接收 runner、channel_manager、身份及两个现有业务服务。两者提供 `from_workspace(workspace)` 工厂，不读文件任务仓库、不注册定时器。
3. 提取纯 `_prune_task_session_state` 及依赖；`LegacyTaskSessionCleaner(repo, session, config, *, lock=None).run(now=None)` 保留旧文件清理行为，`cleanup_legacy_workspace_sessions(workspace)` 是后续可移除的唯一兼容入口。
4. CronManager 继承两个独立实现，保留旧通知定义读取及旧清理方法作为适配，不复制运行逻辑。
5. 验证命令：`venv/bin/python -m pytest tests/unit/app/test_cron_business_services.py tests/unit/app/test_cron_task_session_cleanup.py tests/unit/app/test_system_cron_business.py tests/unit/app/test_scheduled_run_source_system_config_binding.py -q`。

## Task 2：切换新版调用与配置同步（TDD）

Modify: `notification_worker.py`、`system_actions.py`、`managed_session_cleanup.py`、`system_config.py`、`system_bridge.py`、`source_system_config/task_scheduler.py`、`routers/config.py`、`routers/agent.py`。
Test: 相邻通知、系统 action、系统配置 reader/保存、source 清理测试。

1. 通知 worker 新路径继续从数据库取冻结快照；旧路径通过显式兼容仓库取定义，二者都调用独立发送器，不读取 workspace.cron_manager。
2. 系统 action 直接创建 SystemTaskRuntime；source 清理调用独立旧文件适配器后继续数据库清理，异常合并计数顺序不变。
3. 心跳周期转换由独立工具提供；配置保存直接提交既有 system_bridge 刷新，不再借用旧管理器的方法。
4. 不提供旧管理器的工作区中应能完成上述流程；新路径禁止以回退旧类掩盖资源初始化错误。
5. 验证命令：`venv/bin/python -m pytest tests/unit/app/test_cron_notification_worker.py tests/unit/app/test_managed_cron_notifications.py tests/unit/app/test_system_cron_actions.py tests/unit/app/test_system_cron_config_reader.py tests/unit/app/test_system_cron_legacy_cutoff.py tests/unit/app/test_system_cron_config_submission.py tests/unit/app/test_source_system_task_scheduler.py -q`。

## Task 3：回归与交付检查

检查旧管理器仍可直接调用继承方法、配置同步失败仍可见、旧任务清理仍写同样的结果元数据；新运行服务不含 jobs.json 管理和平台操作。执行相关 SWE/Scheduler 系统任务回归、定向 pre-commit、复杂度和 diff 检查。GitNexus impact 已尝试但 WAL 故障不能返回图，依赖通过源码调用点核对；不把主线程自查称为独立子代理评审。

本轮不删除旧 CRUD/CLI/聊天双查询、不升级存量迁移、不停止旧定时器、不拆外部应用。
