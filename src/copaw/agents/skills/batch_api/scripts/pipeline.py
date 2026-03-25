#!/usr/bin/env python3
"""批量API流水线执行器。

支持多步骤串联调用，每个步骤可以使用前序步骤的结果作为输入。

用法:
    python pipeline.py --workdir batch_tasks/my_pipeline
"""

import argparse
import asyncio
import csv
import json
import logging
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class StepConfig:
    """步骤配置。"""
    name: str
    base_url: str
    endpoint: str
    method: str = "GET"
    headers: Dict[str, str] = field(default_factory=dict)
    request_body: Optional[Dict[str, Any]] = None
    url_params: Dict[str, str] = field(default_factory=dict)
    response_data_path: str = "$"
    id_field: str = "id"
    input_source: str = "initial"  # "initial", "previous", 或步骤名
    input_mapping: Dict[str, str] = field(default_factory=dict)
    timeout: float = 30.0
    retry_count: int = 3
    retry_delay: float = 1.0
    concurrency: int = 1
    delay_between_requests: float = 0.0


@dataclass
class PipelineConfig:
    """流水线配置。"""
    steps: List[StepConfig] = field(default_factory=list)


def load_pipeline_config(config_path: Path) -> PipelineConfig:
    """加载流水线配置。"""
    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    steps = []
    for step_data in data.get("steps", []):
        step = StepConfig(
            name=step_data.get("name", f"step_{len(steps)}"),
            base_url=step_data.get("base_url", ""),
            endpoint=step_data.get("endpoint", ""),
            method=step_data.get("method", "GET"),
            headers=step_data.get("headers", {}),
            request_body=step_data.get("request_body"),
            url_params=step_data.get("url_params", {}),
            response_data_path=step_data.get("response_data_path", "$"),
            id_field=step_data.get("id_field", "id"),
            input_source=step_data.get("input_source", "initial"),
            input_mapping=step_data.get("input_mapping", {}),
            timeout=step_data.get("timeout", 30.0),
            retry_count=step_data.get("retry_count", 3),
            retry_delay=step_data.get("retry_delay", 1.0),
            concurrency=step_data.get("concurrency", 1),
            delay_between_requests=step_data.get("delay_between_requests", 0.0),
        )
        steps.append(step)

    return PipelineConfig(steps=steps)


def load_input(input_path: Path) -> List[Dict[str, Any]]:
    """从JSON或CSV文件加载输入数据。"""
    suffix = input_path.suffix.lower()

    if suffix == ".json":
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        raise ValueError("JSON输入必须是列表或包含'data'键")

    elif suffix == ".csv":
        items = []
        with open(input_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                items.append(dict(row))
        return items

    else:
        raise ValueError(f"不支持的输入格式: {suffix}")


def substitute_template(template: str, data: Dict[str, Any]) -> str:
    """替换{字段}占位符。"""
    def replacer(match):
        field_name = match.group(1)
        value = data.get(field_name, "")
        return str(value)
    return re.sub(r"\{(\w+)\}", replacer, template)


def substitute_dict(template: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
    """递归替换字典中的占位符。"""
    result = {}
    for key, value in template.items():
        if isinstance(value, str):
            result[key] = substitute_template(value, data)
        elif isinstance(value, dict):
            result[key] = substitute_dict(value, data)
        elif isinstance(value, list):
            result[key] = [
                substitute_template(item, data) if isinstance(item, str) else item
                for item in value
            ]
        else:
            result[key] = value
    return result


def extract_jsonpath(data: Any, path: str) -> Any:
    """使用简单JSONPath提取数据。"""
    if path == "$":
        return data

    parts = path.lstrip("$.").split(".")
    result = data
    for part in parts:
        if not part:
            continue
        if isinstance(result, dict):
            result = result.get(part)
        elif isinstance(result, list) and part.isdigit():
            result = result[int(part)]
        else:
            return None
    return result


def map_input_data(source_item: Dict[str, Any], mapping: Dict[str, str]) -> Dict[str, Any]:
    """根据映射规则转换输入数据。"""
    if not mapping:
        return source_item

    result = {}
    for target_field, source_path in mapping.items():
        value = extract_jsonpath(source_item, source_path)
        if value is not None:
            result[target_field] = value
    return result


async def make_request(
    client: httpx.AsyncClient,
    step: StepConfig,
    item: Dict[str, Any],
) -> Dict[str, Any]:
    """执行单个API请求。"""
    endpoint = substitute_template(step.endpoint, item)
    url = f"{step.base_url.rstrip('/')}/{endpoint.lstrip('/')}"

    headers = substitute_dict(step.headers, item) if step.headers else {}
    params = substitute_dict(step.url_params, item) if step.url_params else None

    body = None
    if step.request_body and step.method in ("POST", "PUT", "PATCH"):
        body = substitute_dict(step.request_body, item)

    last_error = None
    for attempt in range(step.retry_count):
        try:
            response = await client.request(
                method=step.method,
                url=url,
                headers=headers,
                params=params,
                json=body,
                timeout=step.timeout,
            )
            response.raise_for_status()

            result_data = response.json()
            extracted = extract_jsonpath(result_data, step.response_data_path)

            return {
                "input": item,
                "output": extracted,
                "status": "success",
                "status_code": response.status_code,
            }

        except httpx.HTTPStatusError as e:
            last_error = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
            if e.response.status_code < 500:
                break
        except httpx.RequestError as e:
            last_error = str(e)
        except json.JSONDecodeError:
            last_error = "无效的JSON响应"

        if attempt < step.retry_count - 1:
            await asyncio.sleep(step.retry_delay * (attempt + 1))

    return {
        "input": item,
        "error": last_error,
        "status": "failed",
    }


async def execute_step(
    step: StepConfig,
    input_data: List[Dict[str, Any]],
    output_path: Path,
) -> Dict[str, Any]:
    """执行单个步骤。"""
    results = []
    errors = []
    success_count = 0
    failed_count = 0

    start_time = datetime.now(timezone.utc)

    async with httpx.AsyncClient() as client:
        semaphore = asyncio.Semaphore(min(step.concurrency, 10))

        async def process_item(item: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                result = await make_request(client, step, item)
                if step.delay_between_requests > 0:
                    await asyncio.sleep(step.delay_between_requests)
                return result

        batch_size = max(10, len(input_data) // 10)

        for i in range(0, len(input_data), batch_size):
            batch = input_data[i:i + batch_size]
            batch_results = await asyncio.gather(*[process_item(item) for item in batch])

            for result in batch_results:
                results.append(result)
                if result["status"] == "success":
                    success_count += 1
                else:
                    failed_count += 1
                    errors.append(result)

            logger.info(f"步骤 [{step.name}] 进度: {len(results)}/{len(input_data)} ({success_count} 成功, {failed_count} 失败)")

    end_time = datetime.now(timezone.utc)

    output = {
        "step_name": step.name,
        "status": "completed",
        "total": len(input_data),
        "success": success_count,
        "failed": failed_count,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "duration_seconds": (end_time - start_time).total_seconds(),
        "results": results,
    }

    if errors:
        output["errors"] = errors

    # 保存步骤结果
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    return output


async def run_pipeline(
    pipeline: PipelineConfig,
    initial_input: List[Dict[str, Any]],
    workdir: Path,
) -> Dict[str, Any]:
    """运行完整流水线。"""
    step_results = {}
    current_input = initial_input

    pipeline_start = datetime.now(timezone.utc)
    all_results = {
        "status": "completed",
        "steps": [],
        "start_time": pipeline_start.isoformat(),
    }

    for i, step in enumerate(pipeline.steps):
        logger.info(f"执行步骤 [{i+1}/{len(pipeline.steps)}]: {step.name}")

        # 确定输入数据来源
        if step.input_source == "initial":
            current_input = initial_input
        elif step.input_source == "previous" and i > 0:
            prev_step = pipeline.steps[i - 1]
            prev_result = step_results.get(prev_step.name, {})
            # 展开结果：如果output是数组，展开为多个输入项
            expanded_input = []
            for r in prev_result.get("results", []):
                if r.get("status") != "success":
                    continue
                output = r.get("output")
                if isinstance(output, list):
                    expanded_input.extend(output)
                elif isinstance(output, dict):
                    expanded_input.append(output)
            current_input = expanded_input
        elif step.input_source in step_results:
            source_result = step_results[step.input_source]
            # 展开结果：如果output是数组，展开为多个输入项
            expanded_input = []
            for r in source_result.get("results", []):
                if r.get("status") != "success":
                    continue
                output = r.get("output")
                if isinstance(output, list):
                    expanded_input.extend(output)
                elif isinstance(output, dict):
                    expanded_input.append(output)
            current_input = expanded_input
        # 否则使用当前输入

        # 应用字段映射
        if step.input_mapping and current_input:
            mapped_input = [map_input_data(item, step.input_mapping) for item in current_input]
            current_input = mapped_input

        if not current_input:
            logger.warning(f"步骤 [{step.name}] 没有输入数据，跳过")
            continue

        # 执行步骤
        step_output_path = workdir / f"step_{i+1}_{step.name}.json"
        step_result = await execute_step(step, current_input, step_output_path)
        step_results[step.name] = step_result

        all_results["steps"].append({
            "name": step.name,
            "output_file": str(step_output_path.name),
            "total": step_result["total"],
            "success": step_result["success"],
            "failed": step_result["failed"],
        })

        # 更新当前输入为下一步准备（展开数组）
        expanded_input = []
        for r in step_result.get("results", []):
            if r.get("status") != "success":
                continue
            output = r.get("output")
            if isinstance(output, list):
                expanded_input.extend(output)
            elif isinstance(output, dict):
                expanded_input.append(output)
        current_input = expanded_input

        logger.info(f"步骤 [{step.name}] 完成: {step_result['success']}/{step_result['total']} 成功")

    pipeline_end = datetime.now(timezone.utc)
    all_results["end_time"] = pipeline_end.isoformat()
    all_results["duration_seconds"] = (pipeline_end - pipeline_start).total_seconds()

    return all_results


def main():
    parser = argparse.ArgumentParser(
        description="批量API流水线执行器，支持多步骤串联调用",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--workdir", "-w",
        required=True,
        help="任务目录路径",
    )
    parser.add_argument(
        "--config", "-c",
        help="流水线配置文件名（默认: config.json）",
    )
    parser.add_argument(
        "--input", "-i",
        help="输入文件名（默认: input.json）",
    )
    parser.add_argument(
        "--output", "-o",
        help="最终输出文件名（默认: results.json）",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制覆盖已有输出文件",
    )

    args = parser.parse_args()

    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    config_path = workdir / (args.config or "config.json")
    input_path = workdir / (args.input or "input.json")
    output_path = workdir / (args.output or "results.json")

    if not config_path.exists():
        print(f"错误: 配置文件不存在: {config_path}", file=sys.stderr)
        sys.exit(1)
    if not input_path.exists():
        print(f"错误: 输入文件不存在: {input_path}", file=sys.stderr)
        sys.exit(1)

    if output_path.exists() and not args.force:
        print(f"错误: 输出文件已存在: {output_path}。使用 --force 覆盖。", file=sys.stderr)
        sys.exit(1)

    pipeline = load_pipeline_config(config_path)
    initial_input = load_input(input_path)

    print(f"加载流水线: {len(pipeline.steps)} 个步骤")
    print(f"初始输入: {len(initial_input)} 个项目")

    for i, step in enumerate(pipeline.steps):
        print(f"  步骤 {i+1}: {step.name} ({step.base_url}{step.endpoint})")

    try:
        result = asyncio.run(run_pipeline(pipeline, initial_input, workdir))

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"\n流水线完成!")
        print(f"总耗时: {result['duration_seconds']:.1f} 秒")
        print(f"结果保存至: {output_path}")

        for step_info in result["steps"]:
            print(f"  [{step_info['name']}] {step_info['success']}/{step_info['total']} 成功")

    except KeyboardInterrupt:
        print("\n已中断")
        sys.exit(130)
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()