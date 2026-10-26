# Scheduler 新版接口异常日志

## 边界

- 只补日志，不改变 URL、状态码、响应 JSON、业务流程或配置。
- 接入新版任务查询、管理、控制、分发、三态切换、回调、批次操作、日历、对外查询和三个系统任务路由；旧路由保持现状。
- 复用 `managed/diagnostics.py`，保留异常类型、异常链、数据库错误号和栈位置，不记录原始异常消息、SQL、正文、Cookie、Token 或完整 URL。
- 5xx 为 ERROR，4xx 为 WARNING；正常成功不记录失败日志。操作单返回失败响应时也记录操作 ID、任务 ID、阶段和安全错误码。
- 同一请求只新增一条接口边界日志；业务层已有步骤日志保留，分别用于接口定位和步骤定位。

## 实现步骤

1. 新增 `tests/unit/scheduler/test_api_error_logging.py`：先验证公共路由类缺失导致失败，再覆盖异常转换、依赖失败、失败操作单、校验错误、成功响应和脱敏。
2. 新增 `scheduler/src/scheduler/app/api_logging.py`，以自定义 APIRoute 包裹原处理函数；原异常原样抛出，原 Response 原样返回。不读取请求正文，不消费流式响应。
3. 十二个新版路由声明 `route_class=LoggedAPIRoute`，不修改业务 handler。错误日志使用路由模板、安全路径 ID 和 X-Request-ID/X-B3-TraceId 关联；创建任务的 job_id/operation_id 来自失败操作单。
4. 更新 `analysis/playbook/log-entrypoints.md` 说明日志关键词、字段和已知边界。
5. 运行新增测试、Scheduler 回归、局部 pre-commit、复杂度和 diff 检查。顺序自检，不使用子代理，不将自检称为独立审查。此任务不提交、不推送、不更新行内包。

## 验证命令

```powershell
wsl --cd /mnt/d/Projects/CoPaw env PYTHONPATH=scheduler/src:src:monitor/src venv/bin/python -m pytest tests/unit/scheduler/test_api_error_logging.py -q
wsl --cd /mnt/d/Projects/CoPaw env PYTHONPATH=scheduler/src:src:monitor/src venv/bin/python -m pytest tests/unit/scheduler -q
.venv/Scripts/python.exe -m pre_commit run --config .git/local-hooks/pre-commit-config.yaml --files <本次文件>
git diff --check
```

## 已知限制

GitNexus impact 因索引 WAL 异常失败，改为源码调用点核对。没有连接行内数据库、SWE 或调度平台；本地通过故障注入验证。

## 验证记录

- 首次新增测试因公共日志模块尚不存在而失败；实现后新增 12 项全部通过。
- 查询、管理、控制、回调、分发、模式切换、批次重试和系统任务等相关接口回归：61 项通过。
- Scheduler 全量单元测试：775 项通过、2 项失败。用 HEAD 原始的十二个路由模块及聚合路由在独立 Python 进程内重建后，对照运行仍复现同样两个失败，不修改工作区文件：
  - `test_retry_history_cannot_replace_another_tenant`：测试进入真实模型解析，未配置 SWE 服务地址。
  - Postman 集合的 Workflow 绑定查询用例：测试装配只包含旧 SWE cron 路由，遗漏已拆分的 Workflow 配置路由。
- 本次文件的 pre-commit 全通过（首次运行格式工具改写后复跑通过）；复杂度不超过 15，`git diff --check` 通过。
- 已进行顺序自检，未运行独立子代理审查；未提交、推送或更新行内包。
