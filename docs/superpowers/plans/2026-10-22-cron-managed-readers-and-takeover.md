# 新任务读取、Workflow 路由拆分和存量接管

> 主线程顺序实施，保留上一轮未提交改动，不自动提交、推送或打包。

**Goal:** 完成本轮 3、4、6：业务入口只读 Scheduler 新任务，Workflow 配置独立，存量导入后由 Scheduler 接管。

**Architecture:** 聊天仅保留新来源；SWE 的招呼进度与技能自检使用现有 Scheduler 查询接口，不访问旧管理器。Workflow 配置保持原 URL，拆成独立 router。迁移复用共库管理 journal：SWE 原子写快照及接管意图，Scheduler 后台复用现有管理步骤注册新平台定时器，不回调 SWE 准备资源。

**Spec:** 用户选择 3、4、6；迁移业务 job_id、已有 task_session_id 和 task_chat_id 不得变化。旧外部平台定时器由用户删除，平台新注册 ID 可以变化。

## 约束

- 不修改财富规划发布、CLI/Agent cron 技能，不断开工作区旧管理器启动入口（第 5 项另做）。
- 所有服务共用数据库，不增加回执、数据表、业务缓存或必要配置。
- 迁移不重新创建任务或会话；保留绑定，发现已有绑定冲突则失败，不静默修复。原本没有会话绑定的任务不自动补建。
- 不拿旧平台 ID 当新绑定，不修改或删除旧定时器；批子任务不注册独立批入口。
- 接管持久化可恢复且幂等，普通管理 API 仍不能用指定旧 ID 假装重新创建。
- 前端样式、布局和交互不改，只移除旧查询、旧缓存回退与旧接口标读。
- 先写失败测试，再实现；复杂度不超过 15。GitNexus 不可用时明确以调用源码核对。

## 1. 新任务读取

修改 cronTaskSources/cronTaskActions 及相邻测试：列表、报告归属只读 Scheduler，刷新失败只保留已知新任务，清除旧任务缓存。
新增 SWE managed_query_client.py，完整翻页并校验 tenant/source/agent/owner；招呼任务进度保留既有展示语义，技能自检用新定义进行鉴权和模型检查。
测试：`pnpm --dir console exec vitest run src/api/modules/cronTaskSources.test.ts src/api/modules/cronTaskActions.test.ts --maxWorkers=1`；pytest 新只读客户端、技能自检和招呼进度用例。

## 2. Workflow 配置独立

新增 crons/workflow/api.py，保持 /cron/workflow-bindings/{skill_id} 的 GET/PUT 与身份、响应不变，注册全局与 Agent scoped router。旧 crons.api 仅保留 helper 别名，避免暂未停用的财富规划导入出错，不修改其业务。
测试：独立 router 能在不导入旧任务管理 router 时提供配置，原路径唯一，管理权限与 source 校验不变。

## 3. 共库迁移接管

新增 migration_takeover.py 作为快照仓库的事务依赖：生产迁移 API 启用，旧快照 primitive 可单独验证。校验身份与已有绑定，清空新状态中的旧外部 ID 并留存审计，写标准 update journal，prepared 使用原定义和绑定，management_owner=scheduler，状态 updating。
Scheduler 新增 takeover worker，只处理 migration_takeover 标记的 journal，调用现有 ManagementService，绝不调用 SWE prepare。父批入口按模式注册，子批任务沿用父入口，失败可用原操作重试。管理写入围栏复核迁移原绑定。
异步迁移通过现有 swe_async_task_items 关联自己的接管操作，扫描完成后等待平台注册完成，失败报告 partial_failed；中断保留共库工作，停止不撤销已导入任务。
测试：用真实 SQLite 事务跑导入→后台接管→注册→管理 ready；断言 job/session/chat ID、未读/运行快照不变，无资源准备；重复导入、并发后台不重复注册；普通、暂停批入口、批子任务和绑定冲突覆盖。

## 4. 验证与说明

定向前后端回归、类型检查、pre-commit、导入与既有业务解耦回归。核对没有修改第 1、2、5 项。说明 CLI 当前使用的 SWE 旧接口及请求协议差异，但不改实现。不执行真实业务库 DDL 或外部平台注册。

## 上线验证与边界

1. 迁移前记录原 `job_id`、`meta.task_session_id`、`meta.task_chat_id`，以及 request/dispatch 中原有 session。导入后用同一身份 Header 查询 Scheduler 详情，逐一核对仍为原值；已绑定会话可继续打开原历史。
2. `POST /api/internal/cron/migration/tasks` 提交 `{"operation":"import"}`，持续查询任务状态；`progress.phase=scheduler_takeover` 表示文件扫描完成但平台注册还未完成。最终 `takeover.pending=0`，且 failed=0 才算接管成功。同步分页 import 返回 operation_id 及 takeover_status，写入快照不等于已完成平台注册。
3. 核对新表 owner=scheduler、management_status=ready，以及新外部平台 ID。原任务 ID 和绑定不变；未绑定的任务保持未绑定，不调用 prepare 补会话。verify 对未完成接管返回 takeover_pending，不报已完成。
4. 普通任务按原启用状态注册；批父任务保留开启/暂停状态，批子任务沿用父入口。缺失/未迁移的父入口导致可见失败，不另建独立子入口。旧定时器 ID 留在 journal 审计，不由本次代码删除、暂停或更新。
5. 第 5 项尚未执行，旧工作区启动仍可能恢复旧文件任务。上线须协调旧入口和旧外部定时器停用，防止新旧重复触发；本次不宣称 SWE 已完全摆脱 jobs.json。Scheduler 接管 worker 必须运行，并复用既有 SWE_SCHEDULER_API_URL 供招呼/自检查询（没有新增配置项）。
6. 只运行本地 SQLite/替身验证，不连接行内 MySQL 或真实调度平台。GitNexus 本地索引因 lbug WAL/shadow 不一致暂不可读，本次以源码调用和定向测试核对。
