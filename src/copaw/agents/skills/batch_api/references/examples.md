# 批量API调用示例

---

## 一、单步模式示例

### 示例1：客户信息查询

```bash
mkdir -p batch_tasks/customer_query
```

**config.json:**
```json
{
  "base_url": "https://api.company.com",
  "endpoint": "/v1/customers/{customer_id}",
  "method": "GET",
  "headers": {"Authorization": "Bearer TOKEN"},
  "id_field": "customer_id"
}
```

**input.json:**
```json
[
  {"customer_id": "C001"},
  {"customer_id": "C002"}
]
```

**执行:**
```bash
python scripts/batch_request.py --workdir batch_tasks/customer_query
```

---

### 示例2：CSV输入 + POST请求

**input.csv:**
```csv
product_id,action
P001,check_stock
P002,check_stock
```

**config.json:**
```json
{
  "base_url": "https://api.example.com",
  "endpoint": "/products/action",
  "method": "POST",
  "headers": {"Content-Type": "application/json"},
  "request_body": {
    "product_id": "{product_id}",
    "action": "{action}"
  },
  "id_field": "product_id"
}
```

---

## 二、流水线模式示例

### 示例3：先获取客户列表，再查询详情

**场景**：先调用列表接口获取客户ID，再用ID查询每个客户的详细信息。

```bash
mkdir -p batch_tasks/customer_pipeline
```

**config.json（流水线配置）:**
```json
{
  "steps": [
    {
      "name": "get_customer_list",
      "base_url": "https://api.company.com",
      "endpoint": "/v1/customers",
      "method": "GET",
      "response_data_path": "$.data.items",
      "input_source": "initial"
    },
    {
      "name": "get_customer_details",
      "base_url": "https://api.company.com",
      "endpoint": "/v1/customers/{customer_id}",
      "method": "GET",
      "input_source": "get_customer_list",
      "input_mapping": {
        "customer_id": "$.id"
      }
    }
  ]
}
```

**input.json（初始输入）:**
```json
[{"page": 1, "limit": 100}]
```

**执行:**
```bash
python scripts/pipeline.py --workdir batch_tasks/customer_pipeline
```

**生成的文件:**
```
batch_tasks/customer_pipeline/
├── config.json
├── input.json
├── step_1_get_customer_list.json     # 步骤1结果
├── step_2_get_customer_details.json  # 步骤2结果
└── results.json                      # 最终汇总
```

---

### 示例4：搜索产品后获取库存

**场景**：先搜索产品，再查询每个产品的库存信息。

**config.json:**
```json
{
  "steps": [
    {
      "name": "search_products",
      "base_url": "https://api.shop.com",
      "endpoint": "/products/search",
      "method": "POST",
      "headers": {"Content-Type": "application/json"},
      "request_body": {
        "keyword": "{keyword}",
        "category": "{category}"
      },
      "response_data_path": "$.results",
      "input_source": "initial"
    },
    {
      "name": "check_inventory",
      "base_url": "https://api.shop.com",
      "endpoint": "/inventory/{sku}",
      "method": "GET",
      "input_source": "search_products",
      "input_mapping": {
        "sku": "$.sku"
      }
    }
  ]
}
```

**input.json:**
```json
[
  {"keyword": "手机", "category": "electronics"},
  {"keyword": "笔记本", "category": "computers"}
]
```

---

### 示例5：订单 -> 物流追踪

**场景**：先获取订单列表，再查询每个订单的物流状态。

**config.json:**
```json
{
  "steps": [
    {
      "name": "get_orders",
      "base_url": "https://api.order.com",
      "endpoint": "/orders",
      "method": "GET",
      "url_params": {
        "status": "{status}",
        "date_from": "{date_from}"
      },
      "response_data_path": "$.orders",
      "input_source": "initial"
    },
    {
      "name": "track_shipping",
      "base_url": "https://api.shipping.com",
      "endpoint": "/track/{tracking_number}",
      "method": "GET",
      "input_source": "get_orders",
      "input_mapping": {
        "tracking_number": "$.tracking_no"
      }
    }
  ]
}
```

**input.json:**
```json
[
  {"status": "shipped", "date_from": "2024-01-01"}
]
```

---

### 示例6：三步流水线（用户 -> 订单 -> 详情）

**场景**：获取用户列表 -> 查询每个用户的订单 -> 查询订单详情。

**config.json:**
```json
{
  "steps": [
    {
      "name": "get_users",
      "base_url": "https://api.example.com",
      "endpoint": "/users",
      "input_source": "initial",
      "response_data_path": "$.users"
    },
    {
      "name": "get_user_orders",
      "base_url": "https://api.example.com",
      "endpoint": "/users/{user_id}/orders",
      "input_source": "get_users",
      "input_mapping": {
        "user_id": "$.id"
      },
      "response_data_path": "$.orders"
    },
    {
      "name": "get_order_details",
      "base_url": "https://api.example.com",
      "endpoint": "/orders/{order_id}",
      "input_source": "get_user_orders",
      "input_mapping": {
        "order_id": "$.order_id"
      }
    }
  ]
}
```

**input.json:**
```json
[{"limit": 50}]
```

---

## 三、字段映射详解

`input_mapping` 支持从上一步结果提取字段：

```json
{
  "input_mapping": {
    "customer_id": "$.id",              // 简单字段
    "region": "$.address.province",     // 嵌套字段
    "city": "$.address.city"
  }
}
```

**特殊值**：非JSONPath开头的值作为固定值

```json
{
  "input_mapping": {
    "customer_id": "$.id",
    "source": "api",        // 固定值
    "version": "2.0"        // 固定值
  }
}
```

---

## 四、完整目录结构示例

```
batch_tasks/
├── simple_query/
│   ├── config.json           # 单步配置
│   ├── input.json
│   └── results.json
│
├── customer_pipeline/
│   ├── config.json           # 流水线配置
│   ├── input.json
│   ├── step_1_get_list.json
│   ├── step_2_get_details.json
│   └── results.json
│
└── order_tracking/
    ├── config.json
    ├── input.json
    ├── step_1_get_orders.json
    ├── step_2_track_shipping.json
    └── results.json
```