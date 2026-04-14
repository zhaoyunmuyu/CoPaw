# Swe Playbook

`analysis/playbook/` 用于沉淀重复问题的处理经验，重点记录报错样式、定位入口、日志入口和排查顺序。

## 文档索引

| 文档 | 摘要 |
|------|------|
| [common-errors.md](common-errors.md) | 常见报错模式、典型触发点和第一落点 |
| [location-paths.md](location-paths.md) | 按问题类型给出优先查看的代码路径、配置路径和命令入口 |
| [log-entrypoints.md](log-entrypoints.md) | 运行日志、daemon logs、query error dump、Tracing 的实际入口 |
| [troubleshooting-order.md](troubleshooting-order.md) | 从复现、取证、收敛到验证的推荐顺序 |

## 使用建议

1. 先看 [troubleshooting-order.md](troubleshooting-order.md)，确定排查顺序。
2. 遇到明确错误消息时，再查 [common-errors.md](common-errors.md)。
3. 需要找入口时，看 [location-paths.md](location-paths.md) 和 [log-entrypoints.md](log-entrypoints.md)。
