---
name: skill_optimizer
description: "优化和规范化CoPaw技能。当用户提到'优化skill'、'检查skill'、'skill规范'、'改进skill'，或需要创建新skill、审核现有skill时使用此技能。提供技能规范检查、优化建议、标准模板。"
metadata: { "copaw": { "emoji": "🔧" } }
---

# Skill优化器

## 概述

本skill用于优化和规范化CoPaw的技能文件（SKILL.md），确保所有技能符合统一规范，提高Agent调用准确性。

## 适用场景

- 用户说"帮我优化这个skill"
- 用户说"检查skill是否符合规范"
- 用户说"创建一个新skill"
- 用户说"改进skill的description"
- 需要审核现有skill质量

## 快速开始

### 检查单个skill

```bash
python scripts/check_skill.py --skill <skill名称>
```

### 检查所有skill

```bash
python scripts/check_skill.py --all
```

### 生成优化报告

```bash
python scripts/check_skill.py --skill <skill名称> --report
```

---

## Skill规范标准

### 1. YAML Front Matter

**必需字段**：

```yaml
---
name: skill_name              # 技能名称（小写，下划线分隔）
description: "详细描述..."     # 功能描述 + 触发条件
---
```

**可选字段**：

```yaml
metadata:
  copaw:
    emoji: "📌"               # 显示图标
    requires:
      bins: ["命令名"]         # 需要的CLI工具
      packages: ["包名"]       # 需要的Python包
    install:                   # 安装方式
      - id: brew
        kind: brew
        formula: xxx
```

### 2. description编写规范

**格式**：`功能概述 + 触发条件`

**好的例子**：
```yaml
description: "管理定时任务，创建、查询、暂停、删除cron任务。触发条件：用户提到'定时'、'每天'、'周期性'、'提醒'、'cron'"
```

**差的例子**：
```yaml
description: "CLI to manage cron jobs"  # 无触发条件，语言不一致
```

### 3. 正文结构规范

**推荐结构**：

```markdown
# Skill名称

## 概述
简短说明功能（1-2句话）

## 适用场景
- 场景1：用户说"..."/需要"..."
- 场景2：...
- 场景3：...

## 快速开始
最常用操作（3步以内）

## 详细指南
### 功能1
### 功能2

## 常见问题
| 问题 | 解决方案 |
|------|----------|

## 注意事项
使用限制、安全提示
```

### 4. 检查项清单

| 检查项 | 要求 | 权重 |
|--------|------|------|
| YAML完整 | name, description存在 | 必需 |
| 触发条件 | description包含触发关键词 | 高 |
| 概述章节 | 有"概述"或类似章节 | 高 |
| 适用场景 | 有明确的场景说明 | 中 |
| 快速开始 | 有快速入门步骤 | 中 |
| 代码示例 | 有命令或代码示例 | 中 |
| 常见问题 | 有FAQ或问题解答 | 低 |
| 语言一致 | 全文统一中文或英文 | 中 |

---

## 优化建议

### description优化

**问题**：触发条件不明确

**优化前**：
```yaml
description: "PDF处理工具"
```

**优化后**：
```yaml
description: "处理PDF文件，支持读取、合并、拆分、提取文本。触发条件：用户提到'PDF'、'合并PDF'、'拆分PDF'、'提取PDF文字'"
```

### 结构优化

**问题**：缺少适用场景

**优化前**：
```markdown
# PDF工具

## 命令列表
...
```

**优化后**：
```markdown
# PDF处理

## 概述
处理PDF文件的读取、合并、拆分等操作。

## 适用场景
- 用户需要合并多个PDF
- 用户需要从PDF提取文字
- 用户需要拆分PDF页面

## 快速开始
...
```

---

## Agent工作流程

### 检查并优化现有skill

1. **读取skill文件**：读取目标SKILL.md
2. **运行检查**：分析是否符合规范
3. **生成报告**：列出问题和改进建议
4. **应用优化**：按建议修改文件

### 创建新skill

1. **确认需求**：明确skill功能和触发条件
2. **使用模板**：参考`references/template.md`
3. **填充内容**：按规范编写
4. **检查验证**：确保符合规范

---

## 命令参考

```bash
# 检查单个skill
python scripts/check_skill.py --skill batch_api

# 检查所有skill
python scripts/check_skill.py --all

# 生成详细报告
python scripts/check_skill.py --skill pdf --report

# 输出JSON格式
python scripts/check_skill.py --skill xlsx --json

# 查看帮助
python scripts/check_skill.py --help
```

---

## 常见问题

| 问题 | 解决方案 |
|------|----------|
| description太短 | 添加功能说明和触发关键词 |
| 没有触发条件 | 在description末尾添加"触发条件：..." |
| 结构混乱 | 按标准结构重组：概述→场景→快速开始→详细指南 |
| 语言不一致 | 统一使用中文（推荐）或英文 |
| 缺少代码示例 | 添加常用命令或代码片段 |
| 没有错误处理说明 | 添加"常见问题"章节 |

## 注意事项

- description是Agent判断是否使用skill的关键，务必包含触发词
- 保持简洁，避免冗长的说明
- 代码示例要有注释
- 定期检查skill是否需要更新