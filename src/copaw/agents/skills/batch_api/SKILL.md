---
name: batch_api
description: "当用户需要对大量外部接口进行批量调用时使用此skill。支持单步批量调用和多步骤流水线串联调用。例如：查询数百个客户的信息、先获取客户列表再查询每个客户详情、获取产品列表再查库存等场景。该skill通过脚本自动处理批量执行、进度追踪、错误恢复，并将结果存储到独立任务目录中，不占用模型上下文。触发条件：用户提到'批量'、'循环'、'逐个查询'、'先...再...'、'串联调用'，或有一个列表需要通过API处理。"
---

# 批量API调用指南

## 概述

本skill提供了两种批量API请求模式：

**单步模式**：一次性批量调用同一个接口
- 从JSON/CSV文件读取输入数据
- 基于模板构建URL和请求体
- 进度追踪，支持中断恢复

**流水线模式**：多步骤串联调用
- 支持接口串联，如先调用接口A，再用A的结果调用接口B
- 自动传递数据，支持字段映射
- 每个步骤结果独立存储

**共同特性：**
- 错误处理和自动重试
- 强制独立任务目录
- 结果存储到文件

**适用场景：**
- 需要为10个以上项目调用API查询数据
- 用户提到"批量"、"循环处理"、"逐个查询"
- **先获取列表，再查询详情**（流水线模式）
- **先搜索，再获取详细信息**（流水线模式）

---

## 一、单步模式

适用于一次性批量调用同一接口的场景。

### 工作目录结构

```
batch_tasks/
├── customer_query_20240115/
│   ├── config.json              # 单步配置
│   ├── input.json
│   └── results.json
```

### 配置文件 (config.json)

```json
{
  "base_url": "https://api.example.com",
  "endpoint": "/customers/{customer_id}",
  "method": "GET",
  "headers": {"Authorization": "Bearer TOKEN"},
  "id_field": "customer_id"
}
```

### 执行命令

```bash
python scripts/batch_request.py --workdir batch_tasks/customer_query_20240115
```

### 配置参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `base_url` | string | 必填 | API基础URL |
| `endpoint` | string | 必填 | 端点路径，支持`{字段}`占位符 |
| `method` | string | GET | HTTP方法 |
| `headers` | object | {} | HTTP请求头，支持占位符 |
| `request_body` | object | null | POST/PUT请求体 |
| `url_params` | object | {} | URL查询参数 |
| `response_data_path` | string | "$" | 从响应中提取数据的JSONPath |
| `id_field` | string | "id" | 用于进度追踪的字段名 |
| `timeout` | number | 30 | 请求超时时间（秒） |
| `retry_count` | number | 3 | 失败重试次数 |
| `concurrency` | number | 1 | 并发请求数 |

---

## 二、流水线模式

适用于多步骤串联调用的场景，如先获取列表再查询详情。

### 典型场景

1. **先获取客户ID列表，再逐个查询客户详情**
2. **先搜索产品，再获取每个产品的库存信息**
3. **先获取订单列表，再查询每个订单的物流状态**

### 工作目录结构

```
batch_tasks/
├── customer_details_20240115/
│   ├── config.json              # 流水线配置（含多个步骤）
│   ├── input.json               # 初始输入
│   ├── step_1_get_ids.json      # 步骤1结果（自动生成）
│   ├── step_2_get_details.json  # 步骤2结果（自动生成）
│   └── results.json             # 最终汇总结果
```

### 配置文件格式 (config.json)

```json
{
  "steps": [
    {
      "name": "get_customer_ids",
      "base_url": "https://api.example.com",
      "endpoint": "/customers",
      "method": "GET",
      "response_data_path": "$.data",
      "input_source": "initial"
    },
    {
      "name": "get_customer_details",
      "base_url": "https://api.example.com",
      "endpoint": "/customers/{id}",
      "method": "GET",
      "input_source": "get_customer_ids",
      "input_mapping": {
        "id": "$.id"
      }
    }
  ]
}
```

### 步骤配置参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `name` | string | 步骤名称，用于引用结果 |
| `base_url` | string | API基础URL |
| `endpoint` | string | 端点路径，支持`{字段}`占位符 |
| `method` | string | HTTP方法 |
| `headers` | object | HTTP请求头 |
| `request_body` | object | 请求体 |
| `response_data_path` | string | 从响应提取数据的JSONPath |
| `input_source` | string | 输入来源：`"initial"`（初始输入）、`"previous"`（上一步输出）、步骤名（指定步骤输出） |
| `input_mapping` | object | 字段映射：`{"目标字段": "JSONPath路径"}` |
| `id_field` | string | 用于追踪的字段名 |
| `concurrency` | number | 并发数 |
| `retry_count` | number | 重试次数 |

### 执行命令

```bash
python scripts/pipeline.py --workdir batch_tasks/customer_details_20240115
```

### 字段映射说明

`input_mapping` 用于将上一步的输出映射到当前步骤的输入参数：

```json
{
  "input_mapping": {
    "customer_id": "$.id",           // 从上一步结果提取 id 字段
    "region": "$.address.region",    // 提取嵌套字段
    "type": "vip"                    // 固定值
  }
}
```

---

## 快速开始

### 单步模式示例

```bash
# 1. 创建任务目录
mkdir -p batch_tasks/customer_query

# 2. 创建配置文件
cat > batch_tasks/customer_query/config.json << 'EOF'
{
  "base_url": "https://api.example.com",
  "endpoint": "/customers/{customer_id}",
  "id_field": "customer_id"
}
EOF

# 3. 创建输入文件
cat > batch_tasks/customer_query/input.json << 'EOF'
[{"customer_id": "C001"}, {"customer_id": "C002"}]
EOF

# 4. 执行
python scripts/batch_request.py --workdir batch_tasks/customer_query
```

### 流水线模式示例

```bash
# 1. 创建任务目录
mkdir -p batch_tasks/customer_pipeline

# 2. 创建流水线配置
cat > batch_tasks/customer_pipeline/config.json << 'EOF'
{
  "steps": [
    {
      "name": "list_customers",
      "base_url": "https://api.example.com",
      "endpoint": "/customers",
      "input_source": "initial"
    },
    {
      "name": "get_details",
      "base_url": "https://api.example.com",
      "endpoint": "/customers/{id}",
      "input_source": "list_customers",
      "input_mapping": {"id": "$.id"}
    }
  ]
}
EOF

# 3. 创建初始输入
cat > batch_tasks/customer_pipeline/input.json << 'EOF'
[{"page": 1}]
EOF

# 4. 执行流水线
python scripts/pipeline.py --workdir batch_tasks/customer_pipeline
```

---

## 输出文件格式

### 单步模式 results.json

```json
{
  "status": "completed",
  "total": 200,
  "success": 198,
  "failed": 2,
  "results": [
    {
      "input": {"customer_id": "C001"},
      "output": {"id": "C001", "name": "张三"},
      "status": "success"
    }
  ]
}
```

### 流水线模式 results.json

```json
{
  "status": "completed",
  "steps": [
    {
      "name": "list_customers",
      "output_file": "step_1_list_customers.json",
      "total": 10,
      "success": 10,
      "failed": 0
    },
    {
      "name": "get_details",
      "output_file": "step_2_get_details.json",
      "total": 10,
      "success": 9,
      "failed": 1
    }
  ],
  "duration_seconds": 45.2
}
```

---

## 中断恢复

```bash
# 单步模式
python scripts/batch_request.py --workdir batch_tasks/task1 --resume

# 流水线模式暂不支持中断恢复，需重新执行
```

---

## 命令参考

```bash
# 单步模式
python scripts/batch_request.py --workdir <任务目录>
python scripts/batch_request.py --workdir <任务目录> --resume

# 流水线模式
python scripts/pipeline.py --workdir <任务目录>
python scripts/pipeline.py --workdir <任务目录> --force

# 查看帮助
python scripts/batch_request.py --help
python scripts/pipeline.py --help
```

---

## Agent工作流程

### 单步模式
1. 创建任务目录
2. 创建config.json和input.json
3. 执行batch_request.py
4. 读取results.json汇总结果

### 流水线模式
1. 创建任务目录
2. 创建流水线配置config.json（定义多个steps）
3. 创建初始输入input.json
4. 执行pipeline.py
5. 读取各步骤结果文件和最终results.json