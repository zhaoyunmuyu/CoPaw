# 观测能力与支撑系统

本文档整理不直接位于主执行链路中心、但对可观测性、运维和系统完整性重要的支撑模块。

## 可观测性

| 区域 | 关键文件 | 说明 |
|------|----------|------|
| Tracing | `src/swe/tracing/config.py`, `src/swe/tracing/manager.py`, `src/swe/tracing/models.py`, `src/swe/tracing/model_wrapper.py`, `src/swe/tracing/sanitizer.py`, `src/swe/tracing/store.py` | 追踪配置、模型包装、脱敏和落盘 |
| Token Usage | `src/swe/token_usage/manager.py`, `src/swe/token_usage/model_wrapper.py` | Token 统计与包装器 |
| App 侧心跳 | `src/swe/app/service_heartbeat.py`, `src/swe/app/crons/heartbeat.py` | 服务状态和实例心跳 |

## 调度与后台任务

| 区域 | 关键文件 | 说明 |
|------|----------|------|
| Cron | `src/swe/app/crons/manager.py`, `src/swe/app/crons/executor.py`, `src/swe/app/crons/coordination.py`, `src/swe/app/crons/api.py`, `src/swe/app/crons/models.py` | 定时任务管理、执行与协调 |
| Cron Repo | `src/swe/app/crons/repo/base.py`, `src/swe/app/crons/repo/json_repo.py` | Cron 配置持久化 |
| Instance | `src/swe/app/instance/service.py`, `src/swe/app/instance/store.py`, `src/swe/app/instance/router.py`, `src/swe/app/instance/models.py` | 实例状态与实例管理接口 |
| Backup | `src/swe/app/backup/*.py` | 备份任务、S3 客户端、批处理、Worker 与任务存储 |

## 基础支撑模块

| 目录/文件 | 说明 |
|-----------|------|
| `src/swe/envs/store.py` | 环境变量持久化 |
| `src/swe/tunnel/cloudflare.py`, `src/swe/tunnel/binary_manager.py` | Cloudflare 隧道支持 |
| `src/swe/utils/fs_text.py`, `src/swe/utils/logging.py`, `src/swe/utils/system_info.py`, `src/swe/utils/telemetry.py` | 文件、日志、系统信息与遥测 |
| `src/swe/tokenizer/` | Tokenizer 词表和配置资产 |

## 运维与发布资源

| 目录 | 说明 |
|------|------|
| `deploy/` | Dockerfile、Entrypoint、Supervisor 模板 |
| `scripts/` | 安装、打包、迁移、测试、站点构建脚本 |
| `docs/superpowers/specs/` | 近期开发表设计文档 |

## 关联功能域

- 模型执行链路: [model-provider-and-local-runtime.md](model-provider-and-local-runtime.md)
- 多租户配置与路径体系: [config-and-tenant-isolation.md](config-and-tenant-isolation.md)
