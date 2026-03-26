# Skill模板

这是创建新skill的标准模板，复制此文件并按需修改。

---

```markdown
---
name: skill_name
description: "简短描述skill功能。触发条件：用户提到'关键词1'、'关键词2'、'关键词3'"
metadata:
  copaw:
    emoji: "📌"
    requires:
      bins: []
      packages: []
    install: []
---

# Skill标题

## 概述

用1-2句话说明这个skill的功能。

## 适用场景

- 场景1：用户说"..."/需要"..."
- 场景2：用户需要处理...类型的文件
- 场景3：用户提到"..."相关内容

## 快速开始

最常用的操作步骤，不超过3步。

### 步骤1

操作说明...

```bash
# 示例命令
command --option value
```

### 步骤2

...

## 详细指南

### 功能1

详细说明...

#### 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| param1 | string | 必填 | 参数说明 |
| param2 | int | 10 | 参数说明 |

#### 使用示例

```bash
# 示例1
command --param1 value1

# 示例2
command --param1 value1 --param2 20
```

### 功能2

...

## 常见问题

| 问题 | 解决方案 |
|------|----------|
| 报错"xxx" | 检查...是否正确 |
| 找不到文件 | 确认文件路径是否正确 |
| 权限不足 | 使用sudo或检查文件权限 |

## 注意事项

- 注意事项1
- 注意事项2
- 安全提示

## 参考

- [官方文档](链接)
- `references/xxx.md` - 更多参考资料
```

---

## 创建新Skill步骤

1. **创建目录**
```bash
mkdir -p skills/my_skill/scripts skills/my_skill/references
```

2. **创建SKILL.md**
```bash
# 复制模板并修改
cp skills/skill_optimizer/references/template.md skills/my_skill/SKILL.md
```

3. **编辑内容**
   - 修改name和description
   - 填写适用场景
   - 添加快速开始步骤
   - 编写详细指南
   - 添加常见问题

4. **检查规范**
```bash
python skills/skill_optimizer/scripts/check_skill.py --skill my_skill
```

5. **启用skill**
```bash
copaw skills config
```

---

## Description编写技巧

### 好的Description示例

```yaml
description: "处理Excel文件，支持读取、写入、格式化。触发条件：用户提到'Excel'、'xlsx'、'表格'、'电子表格'"
```

```yaml
description: "批量调用API接口，支持单步模式和流水线模式。触发条件：用户提到'批量'、'循环'、'逐个调用'、'接口串联'"
```

### 差的Description示例

```yaml
description: "Excel工具"  # 太短，无触发条件
```

```yaml
description: "Use this skill for Excel files"  # 无触发条件，语言不一致
```

## 触发词选择建议

| Skill类型 | 推荐触发词 |
|----------|-----------|
| 文件处理 | 文件类型名（PDF、Excel、Word）+ 操作词（打开、读取、转换、合并） |
| API调用 | "批量"、"循环"、"接口"、"API"、"请求" |
| 定时任务 | "定时"、"每天"、"周期"、"提醒"、"cron"、"计划" |
| 数据处理 | "处理"、"分析"、"转换"、"提取"、"生成" |
| 查询搜索 | "查询"、"搜索"、"获取"、"查找"、"列表" |