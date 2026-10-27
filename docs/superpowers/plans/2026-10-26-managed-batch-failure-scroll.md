# 新版批调度失败区域展示修复计划

> 2026-10-26 用户修订：不要新增纵向滚动，按旧看板的分页和长内容省略方式处理。以下为当前实施要求，后文首次滚动方案及其验证记录仅留作被替代方案的背景。

## 修订方案：沿用旧看板分页与省略

- 旧版 `CronBatchDispatch/FailurePanel.tsx` 使用每页 5 条、`ellipsis: true` 控制长错误，不增加纵向滚动。
- 撤销新增的 `FailurePanel.module.less` 滚动样式及根节点的聚焦/滚动属性。
- 新版保留原有字段和每页 5 条；错误分类/错误码、原始错误、类型等列使用固定宽度与单行省略，完整错误由 Tooltip 展示。
- 保留旧版已有的表格横向滚动，不新增纵向滚动，不修改旧版共用样式或重试业务。
- 回归测试：长错误单行展示且悬停可读全文；浏览器核对长错误下 5 条、分页、确认框及操作按钮都在详情区域内，无须纵向滚动。
- 之前桌面生成的 `cron_trans_scroll_local_20261026_161519` 是被替代的滚动方案，不能作为本修订方案交付；本轮不自动重打包。

修订验证：新增“长错误单行省略且悬停可读全文”用例先失败（whiteSpace 不是 nowrap），实现后 3 项 FailurePanel 测试通过。真实浏览器在 1440/1000/700 宽度下，5 行均为 39px，整个失败区高度 490px、内容高度同为 490px，未启用纵向滚动，分页和重试操作可达。TypeScript、Prettier、pre-commit 和差异检查通过。

新旧看板合计 8 个文件、41 项测试串行回归通过。首次并行回归有 1 项页面用例触发默认 5 秒超时；未改断言、超时配置或业务代码，改为 `--maxWorkers=1` 复验全通过。效果截图：`output/playwright/cron-failure-pagination-1440.png`。本轮未提交、推送或更新行内包。

> **For agentic workers:** 使用 superpowers:executing-plans 顺序执行；用户仓库约定不启动子代理。

**Goal:** 新版“失败类型与重试”内容超出详情高度时可以滚动，并到达分页、核实确认及重试按钮。

**Architecture:** 仅在新版 FailurePanel 根节点增加可键盘聚焦的原生滚动容器。使用新版专属 CSS Module 约束高度、启用纵向滚动；沿用表格现有横向滚动、分页和业务处理，不修改旧版共用样式。

**Tech Stack:** React 18、Ant Design 5、Less CSS Modules、Vitest、Playwright。

**Spec:** 用户本轮要求及前一轮诊断：660px 固定外层隐藏溢出，新版失败面板没有纵向滚动，导致底部被裁剪。

## Global Constraints

- 保留既有页面字体、配色、间距和内容顺序，不新增动画。
- 不改接口、重试候选范围、权限和幂等逻辑；表格仍每页 5 条。
- 不修改 `CronBatchDispatch/index.module.less` 或旧版 FailurePanel。
- 既有 Scheduler 日志修改先提交；本轮修复保留为未提交修改，不推送、不打包。
- GitNexus impact/detect-changes 因 WAL 异常无法产出结果，使用源码调用点核对，并明确不是独立子代理审查。

### Task 1: 新版失败区域滚动

**Files:**
- Modify: `console/src/pages/Monitor/ManagedBatchDispatch/FailurePanel.tsx`
- Create: `console/src/pages/Monitor/ManagedBatchDispatch/FailurePanel.module.less`
- Test: `console/src/pages/Monitor/ManagedBatchDispatch/FailurePanel.test.tsx`
- Browser probe: `.git/local-checks/cron-failure-scroll.cjs`（本地校验脚本，不交付生产）

**Interfaces:** 保留 FailurePanel 的 source、batchId、actor、onQueued 入参与所有接口行为；根节点仍是有标签的 section。

- [x] 新增聚焦回归：渲染真实 FailurePanel 后调用 `panel.focus()`，断言 `document.activeElement === panel`；修复前因焦点仍在 body 而失败。
- [x] 浏览器复现：使用真实 BatchDetail/FailurePanel 和共享 CSS，只拦截本地测试 API；修复前面板高度和内容均为 3042px，overflowY=visible，滚轮不能改变 scrollTop，断言失败。
- [x] 最小实现：`className={styles.panel}`、`tabIndex={0}`；专属 `.panel` 使用百分比高度及 border-box，开启纵向滚动，沿用主题色提供键盘焦点轮廓。
- [x] 新版看板 12 项单元测试通过；新旧看板合计 8 个文件、41 项测试通过。TypeScript 类型检查、Prettier 和 `git diff --check` 通过。测试存在 jsdom 不支持伪元素 getComputedStyle 的提示，无断言失败。
- [x] 浏览器验证 1440、1000、700 像素宽度：内容高度 3050/3050/3072px，面板高度 502/488/528px，overflowY=auto，滚轮后 scrollTop 均从 0 增至 450；分页第 2 页、确认框、重试按钮可达，Ctrl+Home 能回到顶部，成员和事件页签切换正常。截图保存到 `output/playwright/`。
- [x] 顺序自检所有差异；`git diff --quiet HEAD -- console/src/pages/Monitor/CronBatchDispatch` 确认旧版目录未变，后端未变。之前的日志修改已提交为 `8fbe27af8`，滚动修复未提交。
